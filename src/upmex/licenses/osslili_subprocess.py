"""
License detection using osslili CLI subprocess.
"""

import logging
import shutil
import sys
import subprocess
import json
import tempfile
import os
from typing import List, Dict, Optional, Any
from pathlib import Path, PurePath

logger = logging.getLogger(__name__)


def osslili_command():
    """The osslili installed alongside upmex, not whichever is on PATH.

    upmex declares osslili as a dependency and then invoked it by bare name,
    so a different copy earlier on PATH answered instead. On this machine that
    was 1.6.1 from a system package manager rather than the 1.7.5 in the
    environment, and the two disagree: the same LICENSE file holding the MIT
    text comes back MIT from one and JSON from the other. Which licence a
    package appears to have should not depend on PATH order.
    """
    beside_the_interpreter = Path(sys.executable).parent / 'osslili'
    for candidate in (beside_the_interpreter,
                      beside_the_interpreter.with_suffix('.exe')):
        # Existing is not the same as runnable. A directory of that name, or a
        # file with no execute bit, would be taken and then fail inside the
        # broad except below, reporting no licence rather than falling back.
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    # Nothing beside the interpreter, so fall back rather than fail outright:
    # upmex still works with osslili installed some other way.
    return shutil.which('osslili') or 'osslili'

# osslili scores a match and also says what kind of evidence it is: a category
# (declared, detected, referenced, third-party) and a match_type saying which
# rule produced it. The score alone is not the whole claim, and it is not even
# stable: the same text scores differently depending on the similarity backend
# available, so gating on the number alone made the reported licence depend on
# which machine ran upmex.
EXACT_DETECTION_METHODS = ('tag', 'spdx_identifier')
HIGH_CONFIDENCE = 0.95

# A licence a file merely mentions, and a licence belonging to bundled
# third-party code, are not this package's licence. Neither becomes one by
# scoring well, so these are refused before any score is considered.
REJECTED_CATEGORIES = ('referenced', 'third-party')

# "declared" is osslili concluding a file states this licence: it is a LICENSE
# file, it is package metadata, it carries an SPDX tag or a full licence
# header, its text matches a licence closely, or metadata pointed at a file
# that does. Each is evidence about what the file is, independent of the score.
#
# One case is not. osslili also labels "declared" any pattern match inside a
# file whose name ends .md, .rst, .txt or .adoc, with match_type
# "documentation". A README saying "this project is licensed under MIT" earns
# that label, so on its own it is a mention, not a declaration.
#
# Listed as the exception rather than as an allowlist of the good ones on
# purpose. osslili has ten declared match types today and adds them over
# releases; an allowlist that fell behind would silently drop real licences,
# which is how a pyproject.toml declaring `license = {file = "LICENSE"}` came
# to be dropped: osslili reports it as package_metadata_file at 0.6.
WEAK_DECLARED_MATCH_TYPES = ('documentation',)

# A document can talk about any licence, including one it does not carry.
# osslili's SPDX patterns match prose as well as tags: "licensed under the
# Apache License, Version 2.0" in a README comes back as detection_method
# "tag", match_type "spdx_identifier", confidence 1.0, indistinguishable in
# the evidence record from a real SPDX-License-Identifier line. An MIT package
# whose README credits a bundled dependency was reported as Apache-2.0.
#
# So inside a document a licence has to be present, not merely named. Naming
# is what osslili cannot tell apart from declaring: its SPDX patterns match
# prose, and its header rule matches "License: X" anywhere in the first thirty
# lines, mid-sentence included. "It bundles terser, license: BSD-2-Clause, for
# minification" is reported exactly as a real SPDX-License-Identifier line is.
#
# Two kinds of evidence survive that. One identifies the file itself, by name
# or by hash, and needs no score. The other is a measured similarity against
# the licence text, which is the one thing a passing mention cannot fake, and
# it is taken only at the top of osslili's scale.
#
# Two match types that sound like they belong here do not.
#
# license_header reads as a promise that the file opens with a licence header,
# and osslili emits it at 0.6 for the lone sentence "the bundled minifier is
# licensed under the Apache License". Inside a document it is another spelling
# of a mention.
#
# documentation is worse, because its score is not comparable between osslili's
# two modes. Scanning one file, a mention scores 0.6 and a document carrying
# the whole licence scores 0.95. Scanning a directory, osslili measures a short
# window around the word "license" instead, and the same mention also scores
# 0.95. No threshold separates them in both modes, so it is refused in each.
#
# The cost, stated plainly: a package whose only licence statement is prose in
# its README, with no licence file and nothing declared in its metadata, is
# read as having no licence when a directory is scanned. Reporting a
# dependency's licence as the package's own is the worse of the two errors.
STRUCTURALLY_THE_LICENCE = ('license_file', 'exact_hash')
CARRIES_LICENCE_TEXT = ('text_similarity',)

# Suffixes osslili scans as text, plus the ones it does not but people write
# documents in anyway. Anchoring on suffix alone missed README with no suffix
# at all, where the credit sentence went straight through.
DOCUMENT_SUFFIXES = (
    '.md', '.markdown', '.mdown', '.rst', '.adoc', '.asciidoc',
    '.txt', '.text', '.textile', '.org', '.me',
)
DOCUMENT_STEMS = (
    'readme', 'install', 'installing', 'changelog', 'changes', 'news',
    'history', 'authors', 'contributors', 'contributing', 'credits',
    'thanks', 'acknowledgements', 'acknowledgments', 'todo', 'faq',
    'security', 'support', 'governance', 'roadmap', 'usage', 'manual',
)

# A licence file is never a document, whatever it is called or suffixed:
# LICENSE.txt, LICENSE-MIT.txt, MIT-LICENSE.md and COPYING all hold the thing
# itself. Refusing those would be the far worse failure.
LICENCE_WORDS = ('license', 'licence', 'copying', 'copyright', 'legal',
                 'notice', 'unlicense', 'unlicence')

# A licence file is often named after the licence and nothing else, and a
# dual-licensed project ships several: MIT.txt beside APACHE.txt. None of them
# contains a licence word, so they need naming.
LICENCE_NAME_STEMS = (
    'mit', 'bsd', 'isc', 'apache', 'apache-2.0', 'gpl', 'lgpl', 'agpl',
    'gplv2', 'gplv3', 'mpl', 'epl', 'cddl', 'ofl', 'cc0', 'cc-by',
    'zlib', 'artistic', 'boost', 'wtfpl', 'zpl', 'psf', 'openssl',
)


def _reads_as_a_document(source_file):
    """A file whose subject is prose, not licence text."""
    if not source_file:
        return False
    name = PurePath(str(source_file).replace('\\', '/')).name
    stem = PurePath(name).stem.lower()
    suffix = PurePath(name).suffix.lower()

    if any(word in stem for word in LICENCE_WORDS):
        return False
    if stem in LICENCE_NAME_STEMS:
        return False
    if suffix in DOCUMENT_SUFFIXES:
        return True
    # No suffix at all, so the name is all there is to go on.
    return not suffix and stem in DOCUMENT_STEMS


# Often confused with Apache-2.0, and never right when it appears.
KNOWN_FALSE_POSITIVES = ('Pixar',)


def is_reportable(lic, spdx_id=None, source_file=None):
    """Whether one piece of osslili evidence is strong enough to report."""
    if spdx_id is None:
        spdx_id = lic.get('detected_license') or lic.get('spdx_id')
    if spdx_id in KNOWN_FALSE_POSITIVES:
        return False

    if lic.get('category') in REJECTED_CATEGORIES:
        return False

    if _reads_as_a_document(
            source_file or lic.get('file') or lic.get('source_file')):
        match_type = lic.get('match_type')
        if match_type in STRUCTURALLY_THE_LICENCE:
            return True
        return (match_type in CARRIES_LICENCE_TEXT
                and lic.get('confidence', 0) >= HIGH_CONFIDENCE)

    if lic.get('detection_method', '') in EXACT_DETECTION_METHODS:
        return True

    if (lic.get('category') == 'declared'
            and lic.get('match_type') not in WEAK_DECLARED_MATCH_TYPES):
        return True

    return lic.get('confidence', 0) >= HIGH_CONFIDENCE



class OssliliSubprocessDetector:
    """License detector using osslili CLI."""
    
    def detect_from_file(self, file_path: str, content: Optional[str] = None, temp_root: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Detect licenses from a file using osslili CLI.
        
        Args:
            file_path: Path to the file (used for naming)
            content: Optional file content to analyze
            
        Returns:
            List of detected licenses with confidence scores
        """
        licenses = []
        
        if content is None:
            return licenses
            
        try:
            # osslili decides what kind of evidence a match is partly from the
            # file's name: LICENSE is a licence file, README.md is a document
            # that mentions one. Writing the content to a random tmpXXXX.txt
            # threw that away, so a package's own LICENSE was read as a passing
            # mention and scored accordingly. Keep the caller's name, inside a
            # directory of our own so nothing collides.
            tmp_dir = tempfile.mkdtemp(dir=temp_root)
            try:
                # '', '.' and '/' have no basename, and '..' is a
                # directory. Writing to either raises, and the broad except
                # below would turn that into a silent empty result.
                tmp_path = os.path.join(
                    tmp_dir, PurePath(file_path).name.strip('.') or 'content'
                )
                with open(tmp_path, 'w') as tmp:
                    tmp.write(content)

                # Run osslili CLI without similarity threshold for better tag detection
                result = subprocess.run(
                    [osslili_command(), '-f', 'evidence', tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout:
                    # Parse JSON output - skip non-JSON header lines
                    stdout_lines = result.stdout.splitlines()
                    json_start = -1
                    for i, line in enumerate(stdout_lines):
                        if line.strip().startswith('{'):
                            json_start = i
                            break
                    
                    if json_start >= 0:
                        json_content = '\n'.join(stdout_lines[json_start:])
                        data = json.loads(json_content)
                    else:
                        data = {}
                    
                    # Extract licenses from evidence format
                    # Handle both 'results' format (older) and 'scan_results' format (newer)
                    if 'scan_results' in data and data['scan_results']:
                        for scan_result in data['scan_results']:
                            if 'license_evidence' in scan_result:
                                for lic in scan_result['license_evidence']:
                                    # Map detected_license to spdx_id for consistency
                                    spdx_id = lic.get('detected_license', lic.get('spdx_id', 'Unknown'))
                                    # osslili reports the file it read, the
                                    # category it assigned and how it matched.
                                    # Overwriting "file" with the path we were
                                    # handed threw away the only way to check
                                    # the claim, and for a synthesised
                                    # document that path is a name we invented.
                                    license_info = {
                                        "name": lic.get('name', spdx_id),
                                        "spdx_id": spdx_id,
                                        "confidence": lic.get('confidence', 0.0),
                                        "confidence_level": self._get_confidence_level(
                                            lic.get('confidence', 0.0),
                                            lic.get('detection_method', ''),
                                            lic.get('match_type', ''),
                                        ),
                                        "source": f"osslili_{lic.get('detection_method', 'unknown')}",
                                        # The content was written to a temp
                                        # file for osslili, so its "file" is
                                        # that path. The name the caller asked
                                        # about is the real one.
                                        "file": file_path,
                                        "category": lic.get('category'),
                                        "match_type": lic.get('match_type'),
                                    }
                                    
                                    if is_reportable(lic, spdx_id, file_path):
                                        licenses.append(license_info)
                    elif 'results' in data and data['results']:
                        # Fallback to old format
                        for result_item in data['results']:
                            if 'licenses' in result_item:
                                for lic in result_item['licenses']:
                                    license_info = {
                                        "name": lic.get('name', lic.get('spdx_id', 'Unknown')),
                                        "spdx_id": lic.get('spdx_id', 'Unknown'),
                                        "confidence": lic.get('confidence', 0.0),
                                        "confidence_level": self._get_confidence_level(
                                            lic.get('confidence', 0.0),
                                            lic.get('detection_method', ''),
                                            lic.get('match_type', ''),
                                        ),
                                        "source": f"osslili_{lic.get('detection_method', 'unknown')}",
                                        # The content was written to a temp
                                        # file for osslili, so its "file" is
                                        # that path. The name the caller asked
                                        # about is the real one.
                                        "file": file_path,
                                        "category": lic.get('category'),
                                        "match_type": lic.get('match_type'),
                                    }
                                    
                                    if is_reportable(lic, source_file=file_path):
                                        licenses.append(license_info)
                        
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                
        except Exception as e:
            logger.debug(f"Osslili subprocess detection failed for {file_path}: {e}")
            
        return licenses
    
    def detect_from_directory(self, dir_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect licenses and copyrights from a directory using osslili CLI.
        
        Args:
            dir_path: Path to the directory
            
        Returns:
            Dictionary with 'licenses' and 'copyrights' lists
        """
        licenses = []
        copyrights = []
        
        try:
            # Run osslili CLI on directory without similarity threshold for better tag detection
            result = subprocess.run(
                [osslili_command(), '-f', 'evidence', '--max-depth', '3', dir_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout:
                # Parse JSON output - skip non-JSON header lines
                stdout_lines = result.stdout.splitlines()
                json_start = -1
                for i, line in enumerate(stdout_lines):
                    if line.strip().startswith('{'):
                        json_start = i
                        break
                
                if json_start >= 0:
                    json_content = '\n'.join(stdout_lines[json_start:])
                    data = json.loads(json_content)
                else:
                    data = {}

                # Debug: Check what we got
                if 'scan_results' in data and data['scan_results']:
                    for sr in data['scan_results']:
                        if 'copyright_evidence' in sr and sr['copyright_evidence']:
                            logger.debug(f"DEBUG: Found copyright evidence: {sr['copyright_evidence']}")
                
                # Extract licenses from evidence format
                seen_licenses = set()
                # Handle both 'scan_results' format (newer) and 'results' format (older)
                if 'scan_results' in data and data['scan_results']:
                    for scan_result in data['scan_results']:
                        if 'license_evidence' in scan_result:
                            for lic in scan_result['license_evidence']:
                                # Map detected_license to spdx_id for consistency
                                spdx_id = lic.get('detected_license', lic.get('spdx_id', 'Unknown'))
                                # Judge before deduplicating. osslili sorts
                                # evidence by score, so keying on the first
                                # record for a (licence, file) pair let a
                                # rejected one stand in for an acceptable one
                                # behind it, and which came first depended on
                                # the machine.
                                if not is_reportable(lic, spdx_id):
                                    continue
                                key = (spdx_id, lic.get('file', 'unknown'))
                                if key in seen_licenses:
                                    continue
                                seen_licenses.add(key)
                                
                                license_info = {
                                    "name": lic.get('name', spdx_id),
                                    "spdx_id": spdx_id,
                                    "confidence": lic.get('confidence', 0.0),
                                    "confidence_level": self._get_confidence_level(
                                        lic.get('confidence', 0.0),
                                        lic.get('detection_method', ''),
                                        lic.get('match_type', ''),
                                    ),
                                    "source": f"osslili_{lic.get('detection_method', 'unknown')}",
                                    # Scanning a directory, so this really is
                                    # the file osslili read.
                                    "file": lic.get('file', 'unknown'),
                                    "category": lic.get('category'),
                                    "match_type": lic.get('match_type'),
                                }
                                
                                licenses.append(license_info)
                elif 'results' in data and data['results']:
                    # Fallback to old format
                    for result_item in data['results']:
                        if 'licenses' in result_item:
                            for lic in result_item['licenses']:
                                # Create unique key to avoid duplicates
                                if not is_reportable(lic):
                                    continue
                                key = (lic.get('spdx_id'), lic.get('source_file'))
                                if key in seen_licenses:
                                    continue
                                seen_licenses.add(key)
                                
                                license_info = {
                                    "name": lic.get('name', lic.get('spdx_id', 'Unknown')),
                                    "spdx_id": lic.get('spdx_id', 'Unknown'),
                                    "confidence": lic.get('confidence', 0.0),
                                    "confidence_level": self._get_confidence_level(
                                        lic.get('confidence', 0.0),
                                        lic.get('detection_method', ''),
                                        lic.get('match_type', ''),
                                    ),
                                    "source": f"osslili_{lic.get('detection_method', 'unknown')}",
                                    "file": lic.get('source_file', 'unknown'),
                                    "category": lic.get('category'),
                                    "match_type": lic.get('match_type'),
                                }
                                
                                licenses.append(license_info)

                # Extract copyrights from scan_results - moved to correct indentation level
                # (This was incorrectly nested inside the 'elif results' block)

                # Now at the correct indentation level - outside of the elif block
                # Extract copyrights from scan_results
                seen_copyrights = set()
                if 'scan_results' in data and data['scan_results']:
                    logger.debug(f"DEBUG: Processing {len(data['scan_results'])} scan results for copyrights")
                    for scan_result in data['scan_results']:
                        if 'copyright_evidence' in scan_result:
                            logger.debug(f"DEBUG: Found {len(scan_result['copyright_evidence'])} copyright items")
                            for copyright_item in scan_result['copyright_evidence']:
                                statement = copyright_item.get('statement', '')
                                logger.debug(f"DEBUG: Processing copyright: statement='{statement}'")
                                if statement and statement not in seen_copyrights:
                                    seen_copyrights.add(statement)
                                    copyright_info = {
                                        "statement": statement,
                                        "holder": copyright_item.get('holder', ''),
                                        "years": copyright_item.get('years', []),
                                        "file": copyright_item.get('file', 'unknown'),
                                        "confidence": copyright_item.get('confidence', 1.0)
                                    }
                                    copyrights.append(copyright_info)
                                    logger.debug(f"DEBUG: Added copyright: {copyright_info}")

            # TODO: OSSlili v1.5.0 doesn't detect "Copyright (c)" format - FIXED in v1.5.1
            # Issue filed: https://github.com/oscarvalenzuelab/osslili/issues/32
        except Exception as e:
            logger.debug(f"Osslili subprocess directory detection failed for {dir_path}: {e}")
            
        return {"licenses": licenses, "copyrights": copyrights}

    # A match is exact when the file says which licence it is, not when a
    # similarity score is close to one. osslili reports which of those it did.
    EXACT_METHODS = frozenset({"tag", "spdx_identifier"})

    def _get_confidence_level(
        self,
        confidence: float,
        detection_method: str = "",
        match_type: str = "",
    ) -> str:
        """How far this is from certain.

        Exact means the text names the licence: an SPDX identifier or a
        licence tag. A similarity score does not become exact by being high,
        and calling 0.988 exact told a consumer that packaging's BSD-2-Clause
        had been read off a declaration when it had been matched against one.
        """
        if detection_method in self.EXACT_METHODS or match_type in self.EXACT_METHODS:
            return "exact"
        if confidence >= 0.95:
            return "high"
        elif confidence >= 0.85:
            return "medium"
        else:
            return "low"
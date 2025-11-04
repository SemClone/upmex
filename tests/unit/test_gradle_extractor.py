"""Tests for Gradle extractor."""

import pytest
from pathlib import Path
from upmex.extractors.gradle_extractor import GradleExtractor
from upmex.core.models import PackageType


class TestGradleExtractor:
    """Test Gradle extractor functionality."""
    
    @pytest.fixture
    def extractor(self):
        """Create a Gradle extractor instance."""
        return GradleExtractor()
    
    @pytest.fixture
    def sample_gradle_groovy(self, tmp_path):
        """Create a sample build.gradle file (Groovy DSL)."""
        gradle_file = tmp_path / "build.gradle"
        gradle_file.write_text("""
plugins {
    id 'java'
    id 'maven-publish'
}

group = 'com.example'
version = '1.0.0'
description = 'Sample Gradle project'

repositories {
    mavenCentral()
}

dependencies {
    implementation 'org.springframework:spring-core:5.3.21'
    implementation 'com.google.guava:guava:31.1-jre'
    testImplementation 'junit:junit:4.13.2'
    runtimeOnly 'mysql:mysql-connector-java:8.0.33'
}

publishing {
    publications {
        maven(MavenPublication) {
            from components.java
            pom {
                name = 'Sample Project'
                description = 'A sample Gradle project for testing'
                url = 'https://github.com/example/sample-project'
                licenses {
                    license {
                        name = 'Apache-2.0'
                        url = 'https://www.apache.org/licenses/LICENSE-2.0.txt'
                    }
                }
                developers {
                    developer {
                        id = 'dev1'
                        name = 'John Doe'
                        email = 'john@example.com'
                    }
                }
                scm {
                    url = 'https://github.com/example/sample-project'
                }
            }
        }
    }
}
""")
        return str(gradle_file)
    
    @pytest.fixture
    def sample_gradle_kotlin(self, tmp_path):
        """Create a sample build.gradle.kts file (Kotlin DSL)."""
        gradle_file = tmp_path / "build.gradle.kts"
        gradle_file.write_text("""
plugins {
    kotlin("jvm") version "1.9.0"
    `maven-publish`
}

group = "org.example"
version = "2.0.0"
description = "Kotlin Gradle project"

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.jetbrains.kotlin:kotlin-stdlib")
    implementation("io.ktor:ktor-server-core:2.3.0")
    testImplementation("org.jetbrains.kotlin:kotlin-test")
    api("org.slf4j:slf4j-api:2.0.7")
}

publishing {
    publications {
        create<MavenPublication>("maven") {
            from(components["java"])
            pom {
                name.set("Kotlin Sample Project")
                description.set("A Kotlin Gradle project for testing")
                url.set("https://gitlab.com/example/kotlin-project")
                licenses {
                    license {
                        name.set("MIT")
                        url.set("https://opensource.org/licenses/MIT")
                    }
                }
                developers {
                    developer {
                        name.set("Jane Smith")
                        email.set("jane@example.org")
                    }
                }
            }
        }
    }
}
""")
        return str(gradle_file)
    
    def test_can_extract_gradle_groovy(self, extractor, sample_gradle_groovy):
        """Test that Gradle Groovy files are recognized."""
        assert extractor.can_extract(sample_gradle_groovy)
    
    def test_can_extract_gradle_kotlin(self, extractor, sample_gradle_kotlin):
        """Test that Gradle Kotlin files are recognized."""
        assert extractor.can_extract(sample_gradle_kotlin)
    
    def test_extract_groovy_metadata(self, extractor, sample_gradle_groovy):
        """Test extraction from Groovy DSL build.gradle."""
        metadata = extractor.extract(sample_gradle_groovy)
        
        assert metadata.package_type == PackageType.GRADLE
        assert metadata.name == "com.example:build"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Sample Gradle project"
        assert metadata.homepage == "https://github.com/example/sample-project"
        assert metadata.repository == "https://github.com/example/sample-project"
        
        # Check dependencies
        assert 'implementation' in metadata.dependencies
        assert 'org.springframework:spring-core:5.3.21' in metadata.dependencies['implementation']
        assert 'com.google.guava:guava:31.1-jre' in metadata.dependencies['implementation']
        assert 'test' in metadata.dependencies
        assert 'junit:junit:4.13.2' in metadata.dependencies['test']
        assert 'runtime' in metadata.dependencies
        assert 'mysql:mysql-connector-java:8.0.33' in metadata.dependencies['runtime']
        
        # Check authors
        assert len(metadata.authors) > 0
        assert metadata.authors[0]['name'] == 'John Doe'
        assert metadata.authors[0]['email'] == 'john@example.com'
        
        # Check license
        assert len(metadata.licenses) > 0
        assert metadata.licenses[0].spdx_id == 'Apache-2.0'
    
    def test_extract_kotlin_metadata(self, extractor, sample_gradle_kotlin):
        """Test extraction from Kotlin DSL build.gradle.kts."""
        metadata = extractor.extract(sample_gradle_kotlin)
        
        assert metadata.package_type == PackageType.GRADLE
        assert metadata.name == "org.example:build"
        assert metadata.version == "2.0.0"
        assert metadata.description == "Kotlin Gradle project"
        assert metadata.homepage == "https://gitlab.com/example/kotlin-project"
        
        # Check dependencies
        assert 'implementation' in metadata.dependencies
        assert 'org.jetbrains.kotlin:kotlin-stdlib' in metadata.dependencies['implementation']
        assert 'io.ktor:ktor-server-core:2.3.0' in metadata.dependencies['implementation']
        assert 'test' in metadata.dependencies
        assert 'org.jetbrains.kotlin:kotlin-test' in metadata.dependencies['test']
        assert 'api' in metadata.dependencies
        assert 'org.slf4j:slf4j-api:2.0.7' in metadata.dependencies['api']
        
        # Check authors
        assert len(metadata.authors) > 0
        assert metadata.authors[0]['name'] == 'Jane Smith'
        assert metadata.authors[0]['email'] == 'jane@example.org'
        
        # Check license
        assert len(metadata.licenses) > 0
        assert metadata.licenses[0].spdx_id == 'MIT'
    
    def test_extract_minimal_gradle(self, extractor, tmp_path):
        """Test extraction from minimal build.gradle."""
        gradle_file = tmp_path / "build.gradle"
        gradle_file.write_text("""
group = 'minimal.example'
version = '0.1.0'

dependencies {
    implementation 'com.example:lib:1.0'
}
""")
        
        metadata = extractor.extract(str(gradle_file))
        
        assert metadata.package_type == PackageType.GRADLE
        assert metadata.name == "minimal.example:build"
        assert metadata.version == "0.1.0"
        assert 'implementation' in metadata.dependencies
        assert 'com.example:lib:1.0' in metadata.dependencies['implementation']
    
    def test_extract_settings_gradle(self, extractor, tmp_path):
        """Test extraction from settings.gradle."""
        settings_file = tmp_path / "settings.gradle"
        settings_file.write_text("""
rootProject.name = 'my-project'
""")
        
        metadata = extractor.extract(str(settings_file))
        
        assert metadata.package_type == PackageType.GRADLE
        assert metadata.name == "my-project"
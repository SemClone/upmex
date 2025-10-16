#!/bin/bash

# Python
curl -L -o requests-2.32.3-py3-none-any.whl "https://files.pythonhosted.org/packages/29/97/32b2c416c5d4108cb01a525da8b9d70c1d19841f0e9e3ce6dc5739312c11/requests-2.32.3-py3-none-any.whl"

# Go
curl -L -o cobra-v1.8.1.zip "https://github.com/spf13/cobra/archive/refs/tags/v1.8.1.zip"
curl -L -o gin-v1.10.0.zip "https://github.com/gin-gonic/gin/archive/refs/tags/v1.10.0.zip"

# Ruby
curl -L -o rails-7.1.5.gem "https://rubygems.org/downloads/rails-7.1.5.gem"

# Rust
curl -L -o serde-1.0.210.crate "https://crates.io/api/v1/crates/serde/1.0.210/download"
curl -L -o tokio-1.41.0.crate "https://crates.io/api/v1/crates/tokio/1.41.0/download"

# Java (already downloaded gson)
curl -L -o guava-33.4.0-jre.jar "https://repo1.maven.org/maven2/com/google/guava/guava/33.4.0-jre/guava-33.4.0-jre.jar"

# .NET
curl -L -o Newtonsoft.Json.13.0.3.nupkg "https://api.nuget.org/v3-flatcontainer/newtonsoft.json/13.0.3/newtonsoft.json.13.0.3.nupkg"
curl -L -o Serilog.3.1.1.nupkg "https://api.nuget.org/v3-flatcontainer/serilog/3.1.1/serilog.3.1.1.nupkg"

echo "All packages downloaded!"

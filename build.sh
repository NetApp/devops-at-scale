#!/bin/bash -e
# Build Script for Devops@Scale solution

version=$1
if [[ -z $version ]]; then
	version="latest"
fi
currentDirectory=`pwd`
clean=$1
docker_build_command='docker build -t'
if [ "$clean" = "clean" ]; then
  docker_build_command='docker build --no-cache -t'
fi

web_service_image_dir="$currentDirectory/web_service"
web_service_image_name="devops-at-scale:${version}"

echo "Building ${web_service_image_name}"
cd $web_service_image_dir && $docker_build_command $web_service_image_name .

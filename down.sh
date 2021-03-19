echo 'Stopping container: '
docker stop les-vehicules
echo 'Removing container: '
docker rm les-vehicules
echo 'Removing image...'
docker rmi $(docker images 'les-vehicules' -aq)
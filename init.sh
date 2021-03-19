echo 'Updating repository...'
git pull origin master
echo 'Revealing secrets, gpg private key must be imported to gpg agent...'
git secret reveal -f
echo 'Building image...'
docker build -t les-vehicules .
echo 'Running, container id:'
docker run -d --name les-vehicules les-vehicules
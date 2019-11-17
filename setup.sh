#!/bin/bash
#Prerequisites
echo "Downloading and compiling required files..."
sudo apt-get install -y git build-essential zlib1g-dev libsdl2-dev libasound2-dev python3-gi pavucontrol
wget https://sourceforge.net/projects/juliusmodels/files/ENVR-v5.4.Dnn.Bin.zip/download
unzip download && rm ./download
cp ./conf-additions/* ./ENVR-v5.4.Dnn.Bin/
pip3 install --upgrade sentry-sdk==0.13.2
git clone https://github.com/julius-speech/julius.git
cd julius
./configure --enable-words-int && make -j4 && echo "ALL DONE"

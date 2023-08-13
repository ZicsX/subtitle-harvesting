#!/bin/bash

# Install the required dependencies
sudo apt update
sudo apt install -y xvfb libgconf-2-4 libxi6 unzip

# Download the ChromeDriver
wget https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip -v

# Unzip the ChromeDriver
unzip chromedriver_linux64.zip

# Move the ChromeDriver to the PATH
sudo mv chromedriver /usr/local/bin/chromedriver

# Test the Selenium setup
python3 -c "import selenium"

echo "Setup completed!"

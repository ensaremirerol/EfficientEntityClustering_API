#!/bin/bash

# Create a virtual environment

python3 -m venv ./.venv

# Activate the virtual environment

source ./.venv/bin/activate

# Install the required packages

pip install -r requirements.txt

# Install eec package

pip install packages/eec/src

# Deactivate the virtual environment

deactivate

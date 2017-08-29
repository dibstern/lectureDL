VENV_NAME=myvenv

python3 -m venv $VENV_NAME
source $VENV_NAME/bin/activate
pip install -r requirements.txt
deactivate


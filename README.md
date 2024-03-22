# Project Setup

This document provides instructions on how to set up and run this project.

## Prerequisites

Ensure you have `pip3` and `python3` installed by running the following commands:

```bash
pip3 -v
python3 -v
```

## Setup

1. Create a Python virtual environment

```python
python3 -m venv venv
```
2. Activate the virtual environment

```python
source venv/bin/activate
```

3. Install the required packages

```python
pip3 install -r requirements.txt
```

## Running the Project

You can run the project from the terminal with the following command:

```python3
python main.py
```

## Create an Executable

To create an exectable file that you can run without opening the IDE, first install `pyinstaller`:

```python
pip3 install pyinstaller
```

Then, use `pyinstaller` to create the executable:

```python
pyinstaller --onefile --add-data 'loading.gif:.' main.py
```
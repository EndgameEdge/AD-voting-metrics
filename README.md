# Delegate Tracking

This repository contains a Python script to track the states of votes cast in polls and spells at SKY.

## Important Note
- The script is not compatible with Python 3.12 due to the deprecation of certain datetime functions used in the code.

## Current Functionality
- Collects information of delegates from vote.sky.money and Dune.
- Retrieves information of polls corresponding to the entered dates from vote.sky.money.
- Retrieves information of spells corresponding to the entered dates from vote.sky.money.
- Exports a CSV file with the SKY holdings of each delegate per date.
- Exports a CSV file with the total SKY ranking of each delegate per date.
- Exports two CSV files (one of them transposed for usability) with the status of the votes corresponding to each poll and spell.

## Requirements
- Python 3.x (versions prior to 3.12) and dependencies listed in `requirements.txt`.

## Installation
Follow these steps to set up the project:
1. Clone the repository:
   ```bash
   git clone 
   ```
1. Navigate to the cloned directory:
   ```bash
   cd AD-voting-metrics
   ```
1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   
## Usage
1. Install the required dependencies from `requirements.txt`.
2. Run `main.py` and follow the on-screen prompts.

## To Dos
- [ ] General code clean up.
- [ ] Add more information about the polls and spells to the CSV file.
# News Tower Modder
Welcome! This is a simple tkinter python project used to mod some parts of the News Tower game. I made this because I beat the game and wanted to fully optimize my newspaper. Without modding, it would have taken forever as it's a game of chance whether you get employees with good traits. Then you have to hope that the colleges are selling the traits you want; which is also only once per week. ...Way too much waiting around for me. 

## Features
This program mainly does two things: allows you to edit employee traits and skill levels, and lets you modify your faction rank. Keep in mind that modifying your faction rank past one of the 'checkpoints' won't really work, likely because there are several internal game state flags that activate the event. I would recommend setting your faction level to one below the next checkpoint, for each checkpoint. 

### Employee Traits
- Allows setting either personality or trainable traits for either slot.
- Bulk employee trait settings

### Employee Skill Levels
- Click on an employee to see their stats and modify their skill levels.

### NPC Faction Level
- Set your level between -8 and 32

## Getting Started
- If you have a new-ish version of python3 and tkinter installed, you can simply run `python3 main.py`.
- If you are unsure, you can try running `./start.sh`. This script simply looks for the most up to date tkinter installation on your mac and uses that version, then runs the program. 

## Notices
- currently mac only, untested on linux or windows. 

## **Extract** scripts
The scripts beginning with extract-* are used for getting factions, jobs+skills, and traits from the game files (once again, mac only). You should run them if there has been a game update since this repo came out or I have updated the default files. That way you can have access to the newest traits, etc. in the mod menu. 

## Further development
I encourage people to fork this or contribute to build it out more. Thank you for your time!
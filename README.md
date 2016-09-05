# lectureDL

## Differences in this fork from original
First, huge praise to @larryhudson for a super handy script. Many of my changes here are preference based, this fork mainly serves as a place for me to fiddle with the script :) Anyway, here's a list of most of the changes:

- A progress indicator for each download.
- Hides the password while the user enters it.
- Detects when a download isn't fully completed, and if so download it again.
- Makes sure echocenter and the list of subjects are fully loaded (on my slow slow slow connection the script would jump the gun on this). This is done by catching the exception for when a css element isn't found. Makes the already great script even more robust.
- Makes the weeks print 01 instead of 1.
- Facilitates automated running of the script with variables modifiable at the top of the file.
- Changes download location to be subject specific. Meaning for a COMP30020 lecture, the script will download it to COMP30020/lectures/lecture name.m4v. This is of course purely a taste based thing.
- Fixes a few bugs by introducing more duck typing. This led to improvements like automatic scrolling when the list of lectures was too long as well as gathering download links significantly faster.
- Added support for partial downloads. Should hopefully be cross platform since I didn't end up using any external libraries.

The whole thing was pretty perfect from the start, so my list of possible improvements here will be short:

- Restructure the code into functions for each abstract task and then have a main which calls these. Would be nice for readability and maintainability's sake.
- Way down the line it would be nice to have a way for it to handle future semesters that don't involve hardcoding date values. Problem for another time!

Again, enormous thanks to @larryhudson for making that something that everybody's always wanted, and for it being so easy to use!

## Setup:
lectureDL is written in [Python 3](http://python.org/downloads) and uses the [Selenium library](http://selenium-python.readthedocs.io) coupled with [ChromeDriver](https://sites.google.com/a/chromium.org/chromedriver/).

The easiest way to install selenium is with pip:
	`pip3 install selenium`

To run lectureDL, download the zip file for this repository and execute the script with Python 3 from inside the directory:
	`python3 lectureDL.py`

Note: I'd recommend hiding subjects that are not active this semester because the script may try to find lecture recordings for past semesters.

![Subject list](img/subj_list_screenshot.png?raw=true "Click on the gear to hide subjects")

## What it does:
* Logs in to Unimelb LMS system
* Builds list of subjects
* For each subject, navigate through to echo system
* Builds list of lectures
* For each lecture, builds filename based on subject number and date and downloads

## Features:
* Assigns week numbers based on date and appends lecture numbers if there are more than one lecture per week - formatted eg. "LING30001 Week 1 Lecture 02.m4v"
* Skips if file already exists
* Can download either video files or audio files
* Allows user to choose specific subjects and to only download lectures for specific weeks

## To do list:
* Allow user to choose download folder
* Replace list system (eg. to_download) with class and attributes?
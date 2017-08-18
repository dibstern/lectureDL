#!/usr/bin/env python3
# lectureDL.py by Larry Hudson
# Python script to download all lecture files, either video or audio
# What it does:
#   Logs in to Unimelb LMS system
#   Builds list of subjects
#   For each subject, navigate through to echo system
#   Builds list of lectures
#   For each lecture, builds filename based on subject number and date and downloads
# Features:
#   Assigns week numbers based on date - formatted eg. "LING30001 Week 1 Lecture 2.m4a"
#   Support for subjects with single or multiple lectures per week
#   Skips if file already exists
#   Can download either video files or audio files
#   Allows user to choose specific subjects and to only download lectures newer than a specific date
# To do list:
#   Allow user to choose download folder
#   Replace list system (eg. to_download) with class and attributes?
#   Change Week numbering from Week 1 to Week 01 (yeah yeah) - best boy Astrid xox

# READ ME (Update as of 2017-07-29):
# If you're modifying this in the future, know first off that the code was
# not designed with easy future use, nor abstraction in general, in mind.
# I've made it a bit better but it's still messy. Assuming you've got the
# required directory structure in place (check out the video_folder variable),
# you'll have to:
# 1. Change the current year and semester if necessary.
# 2. Change the variables representing the start of the semester (such as
#    start_week0 and current_date) for this semester.
# 3. Manually download the latest ChromeDriver and change the driver variable
#    accordingly.
# 4. Perhaps change settings.py.
# While it might be worth it, I feel like it'd be a fair bit of work to
# refactor this project to be "Good TM", after which you could start adding
# extra features. Like imagine trying to catch a selenium error and closing
# chrome if one is encountered, it'd be like a million try/excepts.
# So yeah, maybe one day. Still it wasn't too hard to get it working again.

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementNotVisibleException,
)

import datetime
import getpass
import os.path
import time
import urllib

from collections import defaultdict
from os import listdir
from os import stat
from sys import argv
from sys import exit
from sys import stderr

# Try to read in a settings file.
try:
    from settings import settings
except ImportError:
    settings = defaultdict(lambda: None)


# Setup download folders
home_dir = os.path.expanduser("~")
video_folder = os.path.join(home_dir, "Dropbox/uni2017")
audio_folder = video_folder
lectureFolderName = "lectures"


if not os.path.exists(video_folder):
    conf = input(
        str(video_folder) + ' doesn\'t exist.\nWould you like to use the Downloads folder instead? '
    )[0].lower()
    if conf != 'y':
        print('Ok, shutting down.')
        exit()
    video_folder = os.path.join(home_dir, "Downloads")


def getSubjectFolder(fname):
    subjectCode = fname.split()[0].lower()

    # Using the subject code to find the appropriate folder.
    for i in listdir(video_folder):
        if subjectCode in i or subjectCode.upper() in i:
            subjectFolder = i
            break

    try:
        return subjectFolder
    except NameError:
        print("There is a name mismatch between the subjects list and the folder names.")
        exit(-1)

# Progress bar code from here:
# https://stackoverflow.com/questions/13881092/download-progressbar-for-python-3
# This code is used in the urlretrieve call.
def reporthook(blocknum, blocksize, totalsize):
    readsofar = blocknum * blocksize
    if totalsize > 0:
        percent = readsofar * 1e2 / totalsize
        s = "\r%5.1f%% %*.1f / %.1f MiB" % (
            percent,
            len(str(totalsize)),
            readsofar / 1024 / 1024,
            totalsize / 1024 / 1024,
        )
        stderr.write(s)
        if readsofar >= totalsize: # near the end
            stderr.write("\n")
    else: # total size is unknown
        stderr.write("read %d\n" % (readsofar,))

# define function to find a link and return the one it finds
# works by making a list of the elements and sorts by descending list length,
# so it returns the one with length 1, avoiding the empty lists.
# if it can't find anything, it will return none
def search_link_text(parent, string_list):
    link_elements = []
    for string in string_list:
        link_elements.append(parent.find_elements_by_partial_link_text(string))
    sorted_list = sorted(link_elements, key=len, reverse=True)
    if sorted_list[0] == []:
        return None
    else:
        return sorted_list[0][0]

def show_progress(filehook, localSize, webSize, chunk_size=1024):
    fh = filehook
    total_size = webSize
    total_read = localSize
    while True:
        chunk = fh.read(chunk_size)
        if not chunk:
            fh.close()
            break
        total_read += len(chunk)
        print("Progress: %0.1f%%" % (total_read*100.0/total_size), end="\r")
        yield chunk

# build week number dictionary
current_year = 2017
current_date = datetime.datetime(current_year, 7, 24)
today = datetime.datetime.today(); today_midnight = datetime.datetime(today.year, today.month, today.day)
start_week0 = datetime.datetime(current_year, 7, 17)
end_week0 = datetime.datetime(current_year, 7, 23)
day_delta = datetime.timedelta(days=1)
week_delta = datetime.timedelta(days=7)
week_counter = 1
day_counter = 1
week_day = {}
midsemBreakWeek = 9 # Mid sem break occurs after this week.

# assigns a week number to each date.
while week_counter <= 12:
    while day_counter <= 7:
        week_day[current_date] = week_counter
        day_counter += 1
        current_date = current_date + day_delta
    week_counter += 1
    # If we enter the week of the midsem break, skip a week.
    if week_counter == midsemBreakWeek + 1:
        current_date = current_date + week_delta
    day_counter = 1

# set defaults until user changes them
download_mode = "default"
user_dates_input = "default"
skipped_lectures = []
downloaded_lectures = []

print("Welcome to", argv[0])

# set download mode
while download_mode == "default":
    print("Enter 'v' to download videos or 'a' to download audio")
    if settings['media_type'] is None:
        user_choice = input("> ")
    else:
        print("Using " + settings['media_type'])
        user_choice = settings['media_type']
    if user_choice == "a":
        download_mode = "audio"
    elif user_choice == "v":
        download_mode = "video"
    elif user_choice == "x":
        exit()
    else:
        print("That wasn't an option.")

# old functionality
# specify specific subjects, or download all videos
# while user_subjects == "default":
#   print("Enter subject codes separated by ', ' or leave blank to download all")
#   user_subjects_input = input("> ")
#   if not user_subjects_input == "":
#       user_subjects = user_subjects_input.split(', ')
#   else:
#       user_subjects = []

user_dates_input
# if user enters comma-separated weeks, make a list for each and then concatenate
print("Would you like to download lectures from specific weeks or since a particular date?")
while user_dates_input == "default":
    if settings['date_range'] is None:
        print("Enter a range of weeks (eg. 1-5 or 1,3,4) or a date (DD/MM/2016) to download videos that have since been released.")
        user_dates_input = input("> ")
    else:
        if len(settings['date_range']) > 0:
            print("Using", settings['date_range'])
        else:
            print("Downloading all.")
        user_dates_input = settings['date_range']
    dates_list = []
    if user_dates_input == "":
        # if left blank, download all videos
        dates_list = [start_week0 + datetime.timedelta(n) for n in range(int((datetime.datetime.today() - start_week0).days + 1))]
    elif "," in user_dates_input or user_dates_input.isdigit():
        # if user enters comma-separated weeks, or just one, make a list for each and then concatenate
        print("Lectures will be downloaded for: ")
        chosen_weeks = user_dates_input.replace(" ", "").split(",")
        for item in chosen_weeks:
            start_date = start_week0 + (int(item) * week_delta)
            end_date = end_week0 + (int(item) * week_delta)
            dates_in_week = [start_date + datetime.timedelta(n) for n in range(int((end_date - start_date).days))]
            dates_list += dates_in_week
            print("Week ", item)
        dates_list.append(today_midnight)
    elif "-" in user_dates_input or "/" in user_dates_input:
        # create a table of dates between start date and end date
        if "-" in user_dates_input:
            # splits the start and the end weeks
            chosen_weeks = user_dates_input.split("-")
            start_week = chosen_weeks[0]
            end_week = chosen_weeks[1]
            start_date = start_week0 + (int(start_week) * week_delta)
            end_date = end_week0 + (int(end_week) * week_delta)
        elif "/" in user_dates_input:
            # create a range between start_date and today
            start_date = datetime.datetime.strptime(user_dates_input, "%d/%m/%Y")
            end_date = datetime.datetime.today()
        dates_list = [start_date + datetime.timedelta(n) for n in range(int((end_date - start_date).days))]
        dates_list.append(today_midnight)
        print("Lectures will be downloaded for the dates between " + datetime.datetime.strftime(start_date, "%d %B")
         + " and " + datetime.datetime.strftime(end_date, "%d %B") + ", inclusive.")
    else:
        print("That wasn't an option")
        user_dates_input = "default" # Go back to top of while loop.

# Start Chrome instance
print("Starting up Chrome instance")
driver = webdriver.Chrome("ChromeDriver/chromedriver 2.31")

# login process
print("Starting login process")
driver.get("https://app.lms.unimelb.edu.au")
user_field = driver.find_element_by_css_selector("input[name=user_id]")
if settings['username'] is None:
    settings['username'] = input("Enter your username: ")
user_field.send_keys(settings['username'])
pass_field = driver.find_element_by_css_selector("input[name=password]")
if settings['password'] is None:
    settings['password'] = getpass.getpass("Enter your password: ")
pass_field.send_keys(settings['password'])
print()
pass_field.send_keys(Keys.RETURN)

def getSubjectList():
    # list items in list class "courseListing"
    try:
        course_list_candidates = driver.find_elements_by_css_selector("ul.courseListing")
        if len(course_list_candidates) == 0:
            return [], 0
        # Sometimese there is an invisible dummy subject list that of course
        # lists no subjects. If the style property 'display' is 'none', we
        # know it is the invisble one and we ignore it.
        for c in course_list_candidates:
            if c.value_of_css_property('display') == 'none':
                continue
            course_list = c
        # only get links with target="_top" to single out subject headings
        course_links = course_list.find_elements_by_css_selector('a[target=_top]')
        # list to be appended with [subj_code, subj_name, subj_link]
    except NoSuchElementException:
        # This section must not have loaded yet.
        return [], 0

    subject_list = []
    subj_num = 1

    # get subject info from list of 'a' elements
    for link in course_links:
        # get title eg "LING30001_2016_SM2: Exploring Linguistic Diversity"
        full_string = link.text
        # split at ": " to separate subj_code and subj_name
        middle_split = full_string.split(": ")
        # subj_code == LING30001_2016_SM2, split at "_", string[0]
        subj_code = middle_split[0].split("_")[0]
        # subj_name == Exploring Linguistic Diversity, string[1]
        # join/split method is to account for subjects such as "International Relations: Key Questions"
        subj_name = ": ".join(middle_split[1:])
        # get subject link
        subj_link = link.get_attribute("href")

        # set default for checking against user-specified subjects
        skip_subj = False
        subject_list.append([subj_code, subj_name, subj_link, subj_num])

        subj_num += 1

    return subject_list, len(subject_list)

print("Building list of subjects")
driver.refresh()
# Making sure the subjet list has loaded. It will only equal 1 if not (for biomed in my case).
subject_list, numSubjects = getSubjectList()
# TODO think of a better way to select the lecture stuff and not the community stuff on the right.
while numSubjects < 1:
    subject_list, numSubjects = getSubjectList()
    print("Waiting for subject list to load in LMS...")
    time.sleep(0.5)


# print subjects to download
print("Subject list:")
for item in subject_list:
    # print subject code: subject title
    print(str(item[3]) + ". " + item[0] + ": " + item[1])

# create lists for subjects to be added to
user_subjects = []
skipped_subjects = []

# choose subjects from list
print("Please enter subjects you would like to download (eg. 1,2,3) or leave blank to download all.")
if settings['subject_choices'] is None:
    user_choice = input("> ")
else:
    print("Using " + settings['subject_choices'])
    user_choice = settings['subject_choices']

# for each chosen subj number, check if it is subj_num in subject list, if not skip it, if yes add it to subjects to be downloaded
if not user_choice == "":
    chosen_subj_nums = user_choice.split(",")
    for item in chosen_subj_nums:
        for subj in subject_list:
            if not item == str(subj[3]):
                skipped_subjects.append(subj)
            else:
                user_subjects.append(subj)
else:
    for subj in subject_list:
        user_subjects.append(subj)

print("Subjects to be downloaded:")
for item in user_subjects:
    # print subject code: subject title
    print(item[0] + ": " + item[1])

# for each subject, navigate through site and download lectures
for subj in user_subjects:
    # print status
    print("\nNow working on " + subj[0] + ": " + subj[1])

    # go to subject page and find Lecture Recordings page
    driver.get(subj[2])
    recs_page = search_link_text(driver, ["Lectures", "lectures", "Lecture capture", "Recordings", "recordings", "Capture", "capture"])

    # if no recordings page found, skip to next subject
    if recs_page is None:
        print("No recordings page found, skipping to next subject")
        continue

    recs_page.click()

    # sometimes sidebar links goes directly to echo page, sometimes there's a page in between
    # if there's no iframe, it's on the page in between
    if len(driver.find_elements_by_tag_name("iframe")) == 0:
        links_list = driver.find_element_by_css_selector("ul.contentList")
        recs_page2 = search_link_text(links_list, ["Lectures", "lectures", "Recordings", "Capture", "recordings", "capture"])

        recs_page2.click()

    # now on main page. navigate through iframes
    while True:
        try:
            iframe = driver.find_elements_by_tag_name('iframe')[1]
            driver.switch_to_frame(iframe)
            iframe2 = driver.find_elements_by_tag_name('iframe')[0]
            driver.switch_to_frame(iframe2)
            iframe3 = driver.find_elements_by_tag_name('iframe')[0]
            driver.switch_to_frame(iframe3)
            break
        except:
            time.sleep(0.5)

    # find ul element, list of recordings
    while True:
        try:
            recs_ul = driver.find_element_by_css_selector("ul#echoes-list")
            recs_list = recs_ul.find_elements_by_css_selector("li.li-echoes")
            break
        except NoSuchElementException:
            print("Slow connection, waiting for echocenter to load...")
            time.sleep(0.5)

    # setup for recordings
    subject_code = subj[0]
    multiple_lectures = False
    lectures_list = []
    to_download = [] # will be appended with [first_link, subject_code, week_num, lec_num, date]

    # print status
    print("Building list of lectures...")
    # scroll_wrapper = driver.find_elements
    # driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    # for each li element, build up filename info and add to download list
    for item in recs_list:
        # click on each recording to get different download links
        date_div = item.find_element_by_css_selector("div.echo-date")

        # Deals with error where the next element can't be selected if it isn't literally visible.
        # Weird behaviour, but the solution is to catch the error and tab downwards.
        try:
            date_div.click()
        except ElementNotVisibleException:
            actions = webdriver.ActionChains(driver)
            actions.move_to_element(date_div);
            actions.click()
            actions.send_keys(Keys.SPACE)
            actions.perform()

        # convert string into datetime.datetime object
        # date is formatted like "August 02 3:20 PM" but I want "August 02 2016"
        # so I need to get rid of time and add year
        date_string = " ".join(date_div.text.split(" ")[:-2]) + " " + str(current_year)
        date = datetime.datetime.strptime(date_string, "%d %B %Y")

        # Checking if we can terminate early.
        if date < dates_list[0]:
            print("The lectures further down are outside the date range, no need to check them.")
            break

        #lookup week number and set default lecture number
        week_num = week_day[date]
        lec_num = 1

        # get link to initial download page for either audio or video
        while True:
            try:
                if download_mode == "audio":
                    first_link = driver.find_element_by_partial_link_text("Audio File").get_attribute("href")
                else:
                    first_link = driver.find_element_by_partial_link_text("Video File").get_attribute("href")
                break
            except NoSuchElementException:
                time.sleep(0.5)

        # check if week_num is already in to_download
        for sublist in lectures_list:
            if sublist[2] == week_num:
                # set multiple_lectures to true so that filenames include lecture numbers
                multiple_lectures = True
                # add 1 to lec_num of earlier video
                sublist[3] += 1

        # add info to download list
        lectures_list.append([first_link, subject_code, week_num, lec_num, date])

    # assign filenames
    # made it a separate loop because in the loop above it's constantly updating earlier values etc
    for item in lectures_list:
        filename = item[1] + " Week " + str(item[2]).zfill(2) + " Lecture"
        # Getting the subject folder in which to put the lecture.
        subjectFolder = getSubjectFolder(item[1]) # Item 1 is subject_code.
        # if multiple_lectures == True: Don't worry about this, wasn't implemented properly in the first place.
        # This line would determine whether to append the lecture number to the file name.
        filename = filename + " " + str(item[3])

        if download_mode == "audio":
            filename_with_ext = filename + ".mp3"
            folder = audio_folder
        else:
            filename_with_ext = filename + ".m4v"
            folder = video_folder

        file_path = os.path.join(folder, subjectFolder, lectureFolderName, filename_with_ext)

        if not os.path.isdir(os.path.join(folder, subjectFolder, lectureFolderName)):
            print("Making {} folder for {}".format(lectureFolderName, folder))
            os.makedirs(os.path.join(folder, subjectFolder, lectureFolderName))

        item.append(filename)
        item.append(file_path)

    # only add lectures to be downloaded if they are inside date range. else, skip them
    for item in lectures_list:
        # Append to download list if the file in date range and doesn't exist yet.
        if item[4] in dates_list and not os.path.isfile(item[6]):
            print("Will download", item[5])
            to_download.append((item, False)) # False means not downloaded at all.

        # If the file is in the range but does exist, check that the file is completely
        # downloaded. If not, we will add it to the download list and overwrite the
        # local incomplete version.
        elif item[4] in dates_list and os.path.isfile(item[6]):
            while True:
                try:
                    driver.get(item[0])
                    dl_link = driver.find_element_by_partial_link_text("Download media file.").get_attribute("href")
                    # send javascript to stop download redirect
                    driver.execute_script('stopCounting=true')
                    break
                except:
                    time.sleep(0.5)
            # Check size of file on server. If the server version is larger than the local version,
            # we notify the user of an incomplete file (perhaps the connection dropped or the user
            # cancelled the download). We tell them we're going to download it again.
            # Using wget we could resume the download, but python urllib doesn't have such functionality.
            try:
                f = urllib.request.urlopen(dl_link)
                # This is the size of the file on the server in bytes.
                sizeWeb = int(f.headers["Content-Length"])
            except:
                # Catching the situation where the server doesn't advertise the file length.
                sizeWeb = 0

            # Get size of file on disk.
            statinfo = stat(item[6])
            sizeLocal = statinfo.st_size

            # Add to download list with note that it was incomplete.
            if sizeWeb > sizeLocal:
                item.append("Incomplete file (%0.1f/%0.1f MiB)." % (
                    sizeLocal / 1024 / 1024,
                    sizeWeb / 1024 / 1024,
                ))
                to_download.append((item, (sizeLocal, sizeWeb))) # Include this tuple instead of a Bool if it is partially downloaded.
                print("Resuming " + item[5] + ": " + item[7])
            # Otherwise the file must be fully downloaded.
            else:
                item.append("File already exists on disk (fully downloaded).")
                skipped_lectures.append(item)
                print("Skipping " + item[5] + ": " + item[7])

        # Dealing with other cases.
        else:
            # if both outside date range and already exists
            if not item[4] in dates_list and os.path.isfile(item[6]):
                item.append("Outside date range and file already exists")
            # if just outside date range
            elif not item[4] in dates_list:
                item.append("Outside date range")
            # If file already exists and is fully completed. Shouldn't really get to this case (caught above).
            elif os.path.isfile(item[6]):
                item.append("File already exists")
            skipped_lectures.append(item)
            print("Skipping " + item[5] + ": " + item[7])

    # print list of lectures to be downloaded
    if len(to_download) > 0:
        print("Lectures to be downloaded:")
        for item, partial in to_download:
            # Print with additional note if it's there.
            try:
                print(item[5], "-", item[7])
            # Otherwise just print the lecture name.
            except IndexError:
                print(item[5])
    else:
        print("No lectures to be downloaded.")

    # for each lecture, set filename and download
    for link, partial in to_download:
        # link = [first_link, subject_code, week_num, lec_num, date, filename, file_path]
        # build up filename
        print("Now working on", link[5])
        # go to initial download page and find actual download link
        while True:
            try:
                driver.get(link[0])
                dl_link = driver.find_element_by_partial_link_text("Download media file.").get_attribute("href")
                # send javascript to stop download redirect
                driver.execute_script('stopCounting=true')
                break
            except:
                time.sleep(0.5)

        # Easy to deal with full download, just use urlretrieve. reporthook gives a progress bar.
        if partial == False:
            print("Downloading to", link[6])
            urllib.request.urlretrieve(dl_link, link[6], reporthook)
        # This handles a partially downloaded file.
        else:
            sizeLocal = partial[0]
            sizeWeb = partial[1]
            print("Resuming partial download of %s (%0.1f/%0.1f)." % (link[5], sizeLocal/1000, sizeWeb/1000))

            req = urllib.request.Request(dl_link)
            req.headers['Range'] = 'bytes=%s-' % sizeLocal
            f = urllib.request.urlopen(req)
            # The ab is the append write mode.
            with open(link[6], 'ab') as output:
                for chunk in show_progress(f, sizeLocal, sizeWeb):
                    # Process the chunk
                    output.write(chunk)

        print("Completed! Going to next file!")
        downloaded_lectures.append(link)

    # when finished with subject
    print("Finished downloading files for", subj[1])

# when finished with all subjects
print("All done!")

# [first_link, subject_code, week_num, lec_num, date]
# list downloaded lectures
if len(downloaded_lectures) > 0:
    if len(downloaded_lectures) == 1:
        print("Downloaded 1 lecture:")
    else:
        print("Downloaded " + str(len(downloaded_lectures)) + " lectures:")
    for item in downloaded_lectures:
        print(item[5])

# list skipped lectures
if len(skipped_lectures) > 0:
    if len(skipped_lectures) == 1:
        print("Skipped 1 lecture:")
    else:
        print("Skipped " + str(len(skipped_lectures)) + " lectures:")
    for item in skipped_lectures:
        print(item[5] + ": " + item[7])

driver.quit()

print("\nDone!\n")

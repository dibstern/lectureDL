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

# UPDATE (As of 2017-09-24) - David Stern
# Updates:
# (1) Lecture Class Created & Implemented
# (2) Scrolling Bug Fixed (Long lists of lectures weren't clickable)
# (3) Fixed some constants
# (4) Simplified getSubjectList()
# (5) Require user to re-input choice of subjects, if invalid.
#     As a part of this, broke determine_subjects_to_download() down to
#     include:
#       - getValidUserChoice()  Requests input until valid selection obtained
#       - getSubjects()         Takes the list of subjects, returns only those
#                               selected by the user.
# (6) Switched to f-strings to improve clarity.
# (7) Other unlisted changes.
#
# TODO:
# Create Subject() Class
# Implement Subject() Class
# Implement Graphical Folder Selection
# Implement full GUI
# Fix Dates (Think of a better way to select dates)


from selenium import webdriver
from selenium.webdriver.chrome.options import Options
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
import re

from collections import defaultdict
from os import listdir
from os import stat
from sys import argv
from sys import exit
from sys import stderr
from util import (
    retry_until_result,
    reporthook,
    show_progress,
)

# Try to read in a settings file.
try:
    from settings import settings
except ImportError:
    settings = defaultdict(lambda: None)

LECTURE_TAB_STRINGS = ["Lecture Recordings", "Lecture Capture", "Lectures",
                       "lectures", "Lecture capture", "Recordings",
                       "recordings", "Capture", "capture"]
LECTURE_FOLD_NAME = settings['lecture_subfolder_name']
SUBJ_NAMES = settings['subject_names']
FOLDER_ERROR = (" doesn\'t exist.\nWould you like to use the Downloads" +
                " folder instead? ")
FOLDER_NAME_ERROR = ("There is a name mismatch between the subjects list and" +
                     " the folder names.")

# DAVE_PERSONAL_PREFERENCE
# Enter Video Folder here
UNI_FOLDER = settings['uni_location']


class Lecture(object):

    def __init__(self, link, subjCode, week, lecOfWeek, date, subjName,
                 recNum, fName=None, fPath=None, dl_status=None):
        self.link = link
        self.subjCode = subjCode
        self.week = week
        self.lecOfWeek = lecOfWeek
        self.date = date
        self.subjName = subjName
        self.recNum = recNum
        self.fName = fName
        self.fPath = fPath
        self.dl_status = dl_status

    def __str__(self):
        strFormat = f"{self.subjCode} {self.subjName} - Week {self.week}"
        return strFormat + f" Lecture {self.lecOfWeek}"


def check_uni_folder(uni_folder):
    '''
    @param: uni_folder - pathname generated using os.path
    '''
    if not os.path.exists(uni_folder):
        conf = input(f"{uni_folder}{FOLDER_ERROR}")[0].lower()
        if conf != 'y':
            print('Ok, shutting down.')
            exit()
        uni_folder = os.path.join(home_dir, "Downloads")
    return uni_folder


def getSubjectFolder(fname, uni_folder):

    subjectCode = fname.split()[0].lower()
    print("Getting subject folder")
    print(f"Fname: {fname}, subjectCode: {subjectCode}")
    # Using the subject code to find the appropriate folder.
    for i in listdir(uni_folder):
        if subjectCode in i or subjectCode.upper() in i:
            subjectFolder = i
            break
    try:
        return subjectFolder
    except NameError:
        print(FOLDER_NAME_ERROR)
        exit(-1)


# define function to find a link and return the one it finds
# works by making a list of the elements and sorts by descending list length,
# so it returns the one with length 1, avoiding the empty lists.
# if it can't find anything, it will return none
def search_link_text(browser, query_terms, link_number):
    link_elements = []
    for term in query_terms:
        link_elements.append(browser.find_elements_by_partial_link_text(term))
    sorted_links = sorted(link_elements, key=len, reverse=True)
    if sorted_links[link_number] == []:
        return None
    else:
        return sorted_links[link_number][0]


# Determine download mode.
def get_download_mode():
    valid_options = {'a': 'audio', 'v': 'video'}
    # Using the media_type specified in settings it was set.
    if settings['media_type']:
        return settings['media_type']
    valid = False
    while not valid:
        valid = True
        print("Enter 'v' to download videos or 'a' to download audio.")
        user_choice = input("> ")[0].lower()
        if user_choice in valid_options:
            return valid_options[user_choice]
        else:
            print('That wasn\'t an option.')
            valid = False


# MUCH simpler selection of weeks.
# def select_lectures()


# if user enters comma-separated weeks, make a list for each and then
# concatenate
def get_weeks_to_download(current_year, week_day):
    # TODO break up this god awful huge function.
    # build week number dictionary
    current_date = datetime.datetime(current_year, 7, 24)
    today = datetime.datetime.today()
    today_midnight = datetime.datetime(today.year, today.month, today.day)
    start_week0 = datetime.datetime(current_year, 7, 17)
    end_week0 = datetime.datetime(current_year, 7, 23)
    day_delta = datetime.timedelta(days=1)
    week_delta = datetime.timedelta(days=7)
    week_counter = 1
    day_counter = 1
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

    # The user input stage.
    user_dates_input = "default"
    print("Would you like to download lectures from specific weeks or since a particular date?")
    while user_dates_input == "default":

        # Automatically set the week range if specified in the settings.
        if settings['update_lower_week']:
            lower_week_bound = (datetime.datetime.today() - start_week0).days // 7
            settings['date_range'] =  f"{lower_week_bound}-12"

        # Read in the date range if none was given in the settings.
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

        # if left blank, download all videos
        if user_dates_input == "":
            dates_list = [start_week0 + datetime.timedelta(n) for n in range(int((datetime.datetime.today() - start_week0).days + 1))]

        # if user enters comma-separated weeks, or just one, make a list for each and then concatenate
        elif "," in user_dates_input or user_dates_input.isdigit():
            print("Lectures will be downloaded for: ")
            chosen_weeks = user_dates_input.replace(" ", "").split(",")
            for item in chosen_weeks:
                start_date = start_week0 + (int(item) * week_delta)
                end_date = end_week0 + (int(item) * week_delta)
                dates_in_week = [start_date + datetime.timedelta(n) for n in range(int((end_date - start_date).days))]
                dates_list += dates_in_week
                print("Week ", item)
            dates_list.append(today_midnight)

        # create a table of dates between start date and end date
        elif "-" in user_dates_input or "/" in user_dates_input:

            if "-" in user_dates_input:
                # splits the start and the end weeks
                chosen_weeks = user_dates_input.split("-")
                start_week = chosen_weeks[0]
                end_week = chosen_weeks[1]
                start_date = start_week0 + (int(start_week) * week_delta)
                end_date = end_week0 + (int(end_week) * week_delta)

            # create a range between start_date and today
            elif "/" in user_dates_input:

                start_date = datetime.datetime.strptime(user_dates_input, "%d/%m/%Y")
                end_date = datetime.datetime.today()
            # ???
            dates_list = [start_date + datetime.timedelta(n) for n in range(int((end_date - start_date).days))]
            dates_list.append(today_midnight)
            print("Lectures will be downloaded for the dates between " + datetime.datetime.strftime(start_date, "%d %B")
             + " and " + datetime.datetime.strftime(end_date, "%d %B") + ", inclusive.")
        # Go back to top of while loop.
        else:
            print("That wasn't an option")
            user_dates_input = "default"
    return dates_list


def sign_in(driver):
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


# TODO think of a better way to select the lecture stuff and not the community stuff on the right.
@retry_until_result('Waiting for course list to load...')
def get_course_links(driver):
    # list items in list class "courseListing"
    course_links = None
    try:
        course_list_candidates = driver.find_elements_by_css_selector("ul.courseListing")
        course_list = None
        # Sometimes there is an invisible dummy subject list that of course
        # lists no subjects. If the style property 'display' is 'none', we
        # know it is the invisble one and we ignore it.
        for c in course_list_candidates:
            if c.value_of_css_property('display') == 'none':
                continue
            course_list = c
        if course_list is None:
            return None
        # only get links with target="_top" to single out subject headings
        course_links = course_list.find_elements_by_css_selector('a[target=_top]')
        # list to be appended with [subj_code, subj_name, subj_link]
    except NoSuchElementException:
        # This section must not have loaded yet.
        return None

    return course_links


def getSubjectList(course_links):
    '''Takes the links found on the LMS page belonging to subjects,
       Returns the subject list (with all the information for each)
    '''
    subject_list = []
    for subj_num, link in enumerate(course_links):
        # Turn link text into usable information.
        # E.g. 'POLS20025_2017_SM2: International Relations: Key Questions'
        subj_code, _, _, subj_name = re.split(r"[_:]", link.text, 3)
        subj_name = subj_name.lstrip()
        subj_link = link.get_attribute("href")

        subject_list.append([subj_code, subj_name, subj_link, subj_num+1])

    # They loaded! Don't recurse, return the list instead :)
    return subject_list


def getValidUserChoice():
    while True:
        # Either get the user's choice
        if settings['subject_choices'] is None:
            print("Please enter subjects you would like to download",
                  "(E.g. 1,2,3) or leave blank to download all.")
            user_choice = input("> ")
        # Or use pre-loaded subject choices
        else:
            print(f"Using preloaded setting: {settings['subject_choices']}")
            user_choice = settings['subject_choices']
        # Return the choice if it's valid
        if user_choice == "" or (all(list(map(lambda x: x.isdigit()),
                                          user_choice.split(",")))):
            print("User choice valid!")
            return user_choice
        # If user choice invalid, continue loop.
        else:
            continue


def getSubjects(subject_list):
    '''
    Takes a list of subjects, retrieves a valid selection of subjects from
    the user, and returns just those subjects selected.
    '''
    # Get a user choice
    user_choice = getValidUserChoice()
    # Select specific choices, if they were made
    if user_choice != "":
        # Allows for more flexible input
        selection = [int(x) for x in re.findall(r"\d", user_choice)]
        # TODO:
        # Will need to be changed when Subject() is implemented
        return list(filter(lambda x: any(sel in x for sel in selection),
                           subject_list))
    # If not, just return all of the subjects
    return subject_list


def determine_subjects_to_download(subject_list):
    '''
    Prints candidate subjects for download, before clarifying which subjects
    the user chooses to download.
    '''
    print("Subject list:")
    for subjCode, name, link, sub_num in subject_list:
        print(f"{sub_num}. {subjCode}: {name}")
    return getSubjects(subject_list)





def download_lectures_for_subject(driver, subject, downloaded, skipped,
                                  current_year, week_day, dates_list,
                                  download_mode, video_folder):

    subjCode, name, link, sub_num = subject
    print(f"\nNow working on {subjCode}: {name}")

    # Go to subject page and find Lecture Recordings page.
    driver.get(link)

    main_window = driver.current_window_handle
    link_num = 0
    while True:
        try:
            # Used where code under IndexError is also used (new tabs
            # accidentally opened)
            # driver.switch_to_window(main_window)
            recs_page = search_link_text(driver, LECTURE_TAB_STRINGS, link_num)
            if recs_page is None:
                print("No recordings page found, skipping to next subject")
                return
            recs_page.click()
            time.sleep(.1)

            iframe = driver.find_elements_by_tag_name('iframe')[1]
            driver.switch_to_frame(iframe)
            iframe2 = driver.find_elements_by_tag_name('iframe')[0]
            driver.switch_to_frame(iframe2)
            iframe3 = driver.find_elements_by_tag_name('iframe')[0]
            driver.switch_to_frame(iframe3)
            break

        # Incorrect page opened due to multiple 'Lecture' links. Try next link
        # Untested, because the problem causing this bug mysteriously stopped
        # Could cause main tab to close. This also handles intermediate page
        # errors (because they're viewed as IndexErrors).
        except IndexError:
            # BELOW COMMENTED CODE LEFT IN CASE ERROR ARISES AGAIN
            # Switch tab to the new tab, which we will assume is the next one
            # on the right
            # driver.find_element_by_tag_name('body').send_keys(Keys.CONTROL + Keys.TAB)
            # Close this new tab
            # driver.find_element_by_tag_name('body').send_keys(Keys.CONTROL + 'w')
            link_num += 1

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
    multiple_lectures = False
    lectures_list = []
    to_download = []

    # print status
    print("Building list of lectures...")
    # scroll_wrapper = driver.find_elements
    # driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    # for each li element, build up filename info and add to download list
    for rec_num, recording in enumerate(recs_list):
        # click on each recording to get different download links
        date_div = recording.find_element_by_css_selector("div.echo-date")
        #date_div = recording

        # Deals with error where the next element can't be selected if it isn't
        # literally visible. Weird behaviour, but the solution is to catch the
        # error and tab downwards.
        scroll_point = 10
        while True:
            scroll_point += 5
            try:
                recording.click()
                break
            except ElementNotVisibleException:
                actions = webdriver.ActionChains(driver)
                actions.move_to_element(recording)
                actions.click()
                actions.send_keys(Keys.SPACE)
                actions.perform()
            except:
                driver.execute_script(f"arguments[0].focus();", recs_ul)
                driver.execute_script(f"window.scrollTo(0, {scroll_point});")


        # convert string into datetime.datetime object
        # date is formatted like "August 02 3:20 PM" but I want "August 02 2016"
        # so I need to get rid of time and add year
        date_string = " ".join(date_div.text.split(" ")[:-2]) + f" {current_year}"
        try:
            date = datetime.datetime.strptime(date_string, "%d %B %Y")
        except ValueError:
            # Sometimes the date is presented in different format.
            date = datetime.datetime.strptime(date_string, "%B %d %Y")

        # Checking if we can terminate early.
        # DATE ERROR
        # print(dates_list[0])
        if date < dates_list[0]:
            print("The lectures further down are outside the date range, no need to check them.")
            break

        # lookup week number and set default lecture number
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
        for lecture in lectures_list:
            if lecture.week == week_num:
                # set multiple_lectures to true so filenames include lec nums
                multiple_lectures = True
                # add 1 to lec_num of earlier video
                lecture.lecOfWeek += 1

        # Create Lecture
        lectures_list.append(Lecture(first_link, subjCode, week_num, lec_num,
                                     date, name, rec_num))

    # TODO: Get the length of the <ul>...</ul>, use it when creating the 
    #       lectures instead
    # Fixing Lecture Nums (lecs are downloaded & created in reverse order)
    num_lectures = len(lectures_list)
    for lec in lectures_list:
        lec.recNum = num_lectures - lec.recNum


    # # Getting the subject folder in which to put the lecture.
    # preset_subject_folders = settings['subject_folders']
    # if preset_subject_folders != '':
    #     subjectFolder =
    subjectFolder = getSubjectFolder(lec.subjCode, video_folder)

    # assign filenames
    # made it a separate loop because in the loop above it's constantly
    # updating earlier values etc
    for lec in lectures_list:

        # DAVE_PERSONAL_PREFERENCE
        filename = f"{lec.subjName} - L{lec.recNum:02}"
        # filename = lec.subjCode + " Week " + str(weekNum).zfill(2) + " Lecture"


        # if multiple_lectures == True: Don't worry about this, wasn't implemented properly in the first place.
        # This line would determine whether to append the lecture number to the file name.
        # filename = filename + " " + str(lecNum)

        if download_mode == "audio":
            filename_with_ext = filename + ".mp3"
            folder = audio_folder
        else:
            filename_with_ext = filename + ".m4v"
            folder = video_folder

        file_path = os.path.join(folder, subjectFolder, LECTURE_FOLD_NAME,
                                 filename_with_ext)

        if not os.path.isdir(os.path.join(folder, subjectFolder,
                                          LECTURE_FOLD_NAME)):
            print("Making {} folder for {}".format(LECTURE_FOLD_NAME, folder))
            os.makedirs(os.path.join(folder, subjectFolder, LECTURE_FOLD_NAME))

        lec.fName = filename
        lec.fPath = file_path

    # TODO - This is going into each link even if we don't need the lecture.
    #        This slows the program down massively.
    #        Perhaps filter out those with invalid dates & non-existent files?
    #        A part of this is caused by having to check file sizes every
    #        single time. Get the file sizes once, save into a document, so we
    #        don't have to do this every time.
    # only add lectures to be downloaded if they are inside date range. else,
    # skip them
    for lec in lectures_list:

        # Append to download list if the file in date range and doesn't exist yet.
        if lec.date in dates_list and not os.path.isfile(lec.fPath):
            print(f"Will download {lec.fName}")
            to_download.append((lec, False)) # False means not downloaded at all.

        # If the file is in the range but does exist, check that the file is completely
        # downloaded. If not, we will add it to the download list and overwrite the
        # local incomplete version.
        elif lec.date in dates_list and os.path.isfile(lec.fPath):
            while True:
                try:
                    driver.get(lec.link)
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
            statinfo = stat(lec.fPath)
            sizeLocal = statinfo.st_size

            # Add to download list with note that it was incomplete.
            # TODO Unify the two bits of code to do with downloading / progress.
            if sizeWeb > sizeLocal:
                lec.dl_status = "Incomplete file (%0.1f/%0.1f MiB)." % (
                    sizeLocal / 1024 / 1024,
                    sizeWeb / 1024 / 1024,
                )
                # Include (sizeLocal, sizeWeb) if partially downloaded.
                to_download.append((lec, (sizeLocal, sizeWeb))) 
                print("Resuming " + lec.fName + ": " + lec.dl_status)
            # Otherwise the file must be fully downloaded.
            else:
                lec.dl_status = "File already exists on disk (fully downloaded)."
                skipped.append(lec)
                print("Skipping " + lec.fName + ": " + lec.dl_status)

        # Dealing with other cases.
        else:
            # if both outside date range and already exists
            if not lec.date in dates_list and os.path.isfile(lec.fPath):
                lec.dl_status = "Outside date range and file already exists"
            # if just outside date range
            elif not lec.date in dates_list:
                lec.dl_status = "Outside date range"
            # If file already exists and is fully completed. 
            # Shouldn't really get to this case (caught above).
            elif os.path.isfile(lec.fPath):
                lec.dl_status = "File already exists"
            skipped.append(lec)
            print(f"Skipping {lec.fName}: {lec.dl_status}")

    # print list of lectures to be downloaded
    if len(to_download) > 0:
        print("Lectures to be downloaded:")
        for lec, partial in to_download:
            # Print with additional note if it's there.
            # DAVE_HERE
            if lec.dl_status is not None:
                print(lec.fName, "-", lec.dl_status)
            else:
                print(lec.fName)
    else:
        print("No lectures to be downloaded.")

    # for each lecture, set filename and download
    for lec, partial in to_download:

        # build up filename
        print("Now working on", lec.fName)
        # go to initial download page and find actual download link
        while True:
            try:
                driver.get(lec.link)
                dl_link = driver.find_element_by_partial_link_text("Download media file.").get_attribute("href")
                # send javascript to stop download redirect
                driver.execute_script('stopCounting=true')
                break
            except:
                time.sleep(0.5)

        # Easy to deal with full download, just use urlretrieve. reporthook gives a progress bar.
        if partial == False:
            print("Downloading to", lec.fPath)
            urllib.request.urlretrieve(dl_link, lec.fPath, reporthook)
        # This handles a partially downloaded file.
        else:
            sizeLocal, sizeWeb = partial
            print("Resuming partial download of %s (%0.1f/%0.1f)." % (lec.fName, sizeLocal/1000, sizeWeb/1000))

            req = urllib.request.Request(dl_link)
            req.headers['Range'] = 'bytes=%s-' % sizeLocal
            f = urllib.request.urlopen(req)
            # The ab is the append write mode.
            with open(lec.fPath, 'ab') as output:
                for chunk in show_progress(f, sizeLocal, sizeWeb):
                    # Process the chunk
                    output.write(chunk)

        print("Completed! Going to next file!")
        downloaded.append(lec)

    # when finished with subject
    print("Finished downloading files for", lec.subjCode)
    return downloaded, skipped

# Check dates_list
# The lectures further down are outside the date range, no need to check them.


def main():
    # Setup download folders
    home_dir = os.path.expanduser("~")
    uni_folder = os.path.join(home_dir, UNI_FOLDER)
    video_folder = check_uni_folder(uni_folder)

    print("Welcome to", argv[0])


    # Date Junk
    current_year = datetime.datetime.now().year
    week_day = {}
    dates_list = get_weeks_to_download(current_year, week_day)
    # DATE ERROR
    # print(dates_list)



    download_mode = get_download_mode()

    # Start Chrome instance
    print("Starting up Chrome instance")
    chrome_options = Options()
    window_size = settings.get('window_size', '1600,900')
    chrome_options.add_argument('--window-size=' + window_size)
    if settings['hide_window']:
        print('Running in headless (hidden window) mode.')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')  # TODO: Remove this
    driver = webdriver.Chrome('ChromeDriver/chromedriver 2.31',
                              chrome_options=chrome_options)

    # Login
    print("Starting login process")
    driver.get("https://app.lms.unimelb.edu.au")
    sign_in(driver)
    driver.refresh()
    print("Building list of subjects")

    course_listing = get_course_links(driver)
    subject_list = getSubjectList(course_listing)
    numSubjects = len(subject_list)

    subjects_to_download = determine_subjects_to_download(subject_list)
    print("Subjects to be downloaded:")
    for code, name, link, sub_num in subjects_to_download:
        print(f"{code}: {name}")

    # Track which lectures we downloaded and which we skipped.
    downloaded = []
    skipped = []

    for subject in subjects_to_download:
        loaded, skipd = download_lectures_for_subject(driver, subject,
                                                      downloaded, skipped,
                                                      current_year, week_day,
                                                      dates_list,
                                                      download_mode,
                                                      video_folder)
        downloaded += loaded
        skipped += skipd
    # Done, close the browser.
    print("All done!")
    driver.quit()

    # List the lectures that we downloaded and those we skipped.
    if len(downloaded) > 0:
        if len(downloaded) == 1:
            print("Downloaded 1 lecture:")
        else:
            print(f"Downloaded {len(downloaded)} lectures:")
        for lecture in downloaded:
            print(lecture.fName)

    if len(skipped) > 0:
        if len(skipped) == 1:
            print("Skipped 1 lecture:")
        else:
            print(f"Skipped {len(skipped)} lectures:")
        for lecture in skipped:
            print(lecture.fName + ": " + lecture.dl_status)

    print("\nDone!\n")


if __name__ == '__main__':
    main()

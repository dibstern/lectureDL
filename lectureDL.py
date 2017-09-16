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
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementNotVisibleException,
)

import datetime
import functools
import getpass
import os.path
import time
import urllib

from collections import defaultdict
from os import listdir
from os import stat
from queue import Queue
from sys import argv
from sys import exit
from sys import stderr
from threading import Thread
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

LECTURE_TAB_STRINGS = ["Lectures", "lectures", "Lecture capture", "Recordings", "recordings", "Capture", "capture"]
lectureFolderName = "lectures"


def check_video_folder(video_folder):
    if not os.path.exists(video_folder):
        conf = input(
            str(video_folder) + ' doesn\'t exist.\nWould you like to use the Downloads folder instead? '
        )[0].lower()
        if conf != 'y':
            print('Ok, shutting down.')
            exit()
        video_folder = os.path.join(home_dir, "Downloads")
    return video_folder


def getSubjectFolder(fname, video_folder):
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

# old functionality
# specify specific subjects, or download all videos
# while subjects_to_download == "default":
#   print("Enter subject codes separated by ', ' or leave blank to download all")
#   subjects_to_download_input = input("> ")
#   if not subjects_to_download_input == "":
#       subjects_to_download = subjects_to_download_input.split(', ')
#   else:
#       subjects_to_download = []

# if user enters comma-separated weeks, make a list for each and then concatenate
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
            settings['date_range'] = str(lower_week_bound) + '-12'
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


# TODO think of a better way to select the lecture stuff and not the community stuff on the right.
def getSubjectList(course_links):
    # Gets the subject list (with all the information for each).
    # We expect the input argument (course_listing) to be properly populated.

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

    # They loaded! Don't recurse, return the list instead :)
    return subject_list


def determine_subjects_to_download(subject_list):
    # Print candidate subjects for download.
    print("Subject list:")
    for item in subject_list:
        # print subject code: subject title
        print(str(item[3]) + ". " + item[0] + ": " + item[1])
    # Create lists to hold the subjects we're downloading and skipping.
    subjects_to_download = []
    skipped_subjects = []
    # choose subjects from list
    print("Please enter subjects you would like to download (eg. 1,2,3) or leave blank to download all.")
    if settings['subject_choices'] is None:
        user_choice = input("> ")
    else:
        print("Using " + settings['subject_choices'])
        user_choice = settings['subject_choices']
    # For each chosen subject number, check if it is subj_num in subject list.
    # If not, skip it. If yes, add it to subjects to be downloaded.
    if not user_choice == "":
        chosen_subj_nums = user_choice.split(",")
        for item in chosen_subj_nums:
            for subject in subject_list:
                if not item == str(subject[3]):
                    skipped_subjects.append(subject)
                else:
                    subjects_to_download.append(subject)
    else:
        for subject in subject_list:
            subjects_to_download.append(subject)
    return subjects_to_download


def download_full(dl_link, output_name):
    print("Downloading to", output_name)
    urllib.request.urlretrieve(dl_link, output_name, reporthook)


def download_partial(dl_link, output_name, pretty_name, sizeLocal, sizeWeb):
    print("Resuming partial download of %s (%0.1f/%0.1f)." % (pretty_name, sizeLocal/1000, sizeWeb/1000))

    req = urllib.request.Request(dl_link)
    req.headers['Range'] = 'bytes=%s-' % sizeLocal
    f = urllib.request.urlopen(req)
    # The ab is the append write mode.
    with open(output_name, 'ab') as output:
        for chunk in show_progress(f, sizeLocal, sizeWeb):
            # Process the chunk
            output.write(chunk)
    f.close()


def download_lectures_for_subject(driver, subject, downloaded, skipped, current_year, week_day, dates_list, download_mode, video_folder, q):
    print("\nNow working on " + subject[0] + ": " + subject[1])

    # Go to subject page and find Lecture Recordings page.
    driver.get(subject[2])

    # If the window is too small we need to make the sidebar visible.
    try:
        recs_page = search_link_text(driver, LECTURE_TAB_STRINGS)
        recs_page.click()
    except:
        pullers = driver.find_elements_by_id("menuPuller")
        for i in pullers:
            i.click()
        time.sleep(1)  # TODO this is very falky.
        recs_page = search_link_text(driver, LECTURE_TAB_STRINGS)
        recs_page.click()

    # if no recordings page found, skip to next subject
    if recs_page is None:
        print("No recordings page found, skipping to next subject")
        return

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
    subject_code = subject[0]
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
        try:
            date = datetime.datetime.strptime(date_string, "%d %B %Y")
        except ValueError:
            # Sometimes the date is presented in different format.
            date = datetime.datetime.strptime(date_string, "%B %d %Y")

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
        subjectFolder = getSubjectFolder(item[1], video_folder) # Item 1 is subject_code.
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
            # TODO Unify the two bits of code to do with downloading / progress.
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
                skipped.append(item)
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
            skipped.append(item)
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
            dl_func = functools.partial(download_full, dl_link, link[6])
        # This handles a partially downloaded file.
        else:
            dl_func = functools.partial(download_partial, dl_link, link[6], link[5], partial[0], partial[1])

        print("Queued! Going to next file!")
        downloaded.append(link)
        q.put(dl_func)

    # when finished with subject
    print("Finished downloading files for", subject[1])


def consume_dl_queue(q):
    # This will just keep consuming an item from the queue and downloading it
    # until the program ends. get() blocks if there isn't an item in the queue.
    while True:
        dl_func = q.get()
        res = dl_func()
        if res is False:
            break

def main():
    # Setup download folders
    home_dir = os.path.expanduser("~")
    video_folder = os.path.join(home_dir, "Dropbox/uni2017")
    audio_folder = video_folder

    print("Welcome to", argv[0])
    video_folder = check_video_folder(video_folder)

    current_year = datetime.datetime.now().year
    week_day = {}
    dates_list = get_weeks_to_download(current_year, week_day)

    download_mode = get_download_mode()

    # Start Chrome instance
    print("Starting up Chrome instance")
    chrome_options = Options()
    window_size = settings.get('window_size', '1600,900')
    chrome_options.add_argument('--window-size=' + window_size)
    if settings['hide_window']:
        print('Running in headless (hidden window) mode.')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')  # TODO Remove this one day.
    driver = webdriver.Chrome('ChromeDriver/chromedriver 2.31', chrome_options=chrome_options)

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
    for item in subjects_to_download:
        # print subject code: subject title
        print(item[0] + ": " + item[1])

    # Track which lectures we downloaded and which we skipped.
    downloaded = []
    skipped = []

    q = Queue()
    t = Thread(target=consume_dl_queue, args=(q,))
    t.start()
    for subject in subjects_to_download:
        download_lectures_for_subject(driver, subject, downloaded, skipped, current_year, week_day, dates_list, download_mode, video_folder, q)

    # Let the thread know that we're done.
    q.put(lambda: False)
    # Wait for all the downloads to complete.
    t.join()
    # Done, close the browser.
    print("All done!")
    driver.quit()

    # [first_link, subject_code, week_num, lec_num, date]
    # List the lectures that we downloaded and those we skipped.
    if len(downloaded) > 0:
        if len(downloaded) == 1:
            print("Downloaded 1 lecture:")
        else:
            print("Downloaded " + str(len(downloaded)) + " lectures:")
        for item in downloaded:
            print(item[5])

    if len(skipped) > 0:
        if len(skipped) == 1:
            print("Skipped 1 lecture:")
        else:
            print("Skipped " + str(len(skipped)) + " lectures:")
        for item in skipped:
            print(item[5] + ": " + item[7])

    print("\nDone!\n")


if __name__ == '__main__':
    main()

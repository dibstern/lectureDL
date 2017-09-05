# To do list
* Command-line arguments: adding a main function, as well as a way to pass in settings before running the script so that the user does not have to wait for the script to run.
* Move some of the repeated code into defined functions for more flexibility, reusability of code
* ~Let the user save the username and password to a separate file~
* ~Download progress bar~
* Combine comma-separated weeks and week ranges so that input such as '1, 3-5' can be handled
* ~Detect if files did not finish downloading, resume or restart them if needed~

## Update
I imagine a future with a new model, probably multithreaded.

It would have two threads/processes running at the same time:

1. This thread trawls the LMS collecting download links.
2. This thread maintains a queue which actually downloads using those links.

This model would mean you can start downloading the moment you get your first link. Furthermore, after you get all the links for a subject, you don't have to wait for the last download to finish, you can just move on to the next subject.

I imagine that thread 1 would maybe pass some sort of `Download` object to the queue which would have not just the link, but the filename/filepath for that download, and any other necessary information.

#Marxist Ebook Scraper

Use this script alongside Calibre to pull any number of articles from [Marxists.org](marxists.org) and convert them into a single ebook.

##Requirements

In addition to the python libraries listed in requirements.txt, this script requires [Calibre](https://calibre-ebook.com/) and its add-on [EpubMerge](https://www.mobileread.com/forums/showthread.php?t=169744). Right now the executables "ebook-merge" and "calibre-debug" must be in your path.

Marxist Ebook

##Usage

python3 marxistbook.py [-h] [-o OUTPUT] [-t TITLE] [-a AUTHOR] url [url ...]

positional arguments:

  url                   urls to download

optional arguments:

  -h, --help
  
                        show this help message and exit
  
  -o OUTPUT, --output OUTPUT
  
                        name of output file
                        
  -t TITLE, --title TITLE
  
                        set the title manually
                        
  -a AUTHOR, --author AUTHOR
  
                        set the author manually (currently not working)

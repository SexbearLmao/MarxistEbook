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

URLs should be one of two types: a table of contents, or an actual article.
A table of contents is a page like [this one](https://www.marxists.org/archive/lenin/works/1914/self-det/index.htm).
Each chapter will be downloaded individually, the links at the bottom of the page will be removed, and they will be merged into a single book.
An article is a page like [this](https://www.marxists.org/archive/lenin/works/1912/jun/17.htm), which contains the actual text.
URLs of both types can be combined in any order. Each URL will be downloaded and made into an epub individually, then they will all be merged into a single book.
This book will be either converted or renamed, based on the output filetype.

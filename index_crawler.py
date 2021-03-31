from sys import argv
import requests
from lxml.html import tostring, document_fromstring
from argparse import ArgumentParser
import random
import subprocess
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import os
import os.path
from queue import SimpleQueue, Empty

class TaskItems:
    def __init__(self, errors404: SimpleQueue, store_images: bool =False,
        trim: bool =True):
        self.errors404 = errors404
        self.store_images = store_images
        self.trim = trim

def rand_name():
    return '%030x' % random.randrange(16**30)

#quote cli args that contain strings so they display nicely when printing
#does not affect the actual arguments sent to subprocess.run
def quote_arg(s):
    if ' ' in s:
        return '"{}"'.format(s)
    return s

def trim_chapter(root):
    #find by comment
    try:
        comments = root.xpath('//comment()')
        foot = next(filter(lambda e: 't2h-foot ' in e.text, comments))
        parent = foot.getparent()
        prev = foot.getprevious()
        while prev.getnext() is not None:
            parent.remove(prev.getnext())
    except StopIteration:
        pass
    #find by class
    try:
        pars = root.xpath('//p')
        footers = [foot for foot in pars if 'footer' in foot.classes]
        for foot in footers:
            parent = foot.getparent()
            parent.remove(foot)
    except StopIteration:
        pass
    

def process_chapter(url, taskItems: TaskItems =None):
    assert(url)
    base_name = rand_name()
    html_name = base_name + '.html'
    epub_name = base_name + '.epub'
    try:
        print('downloading {}'.format(url))
        resp = requests.get(url)
        if resp.status_code != 200:
            if resp.status_code == 404:
                print('received 404, skipping {}'.format(url))
                if taskItems:
                    taskItems.errors404.put(url)
                return ''
            print('received error code {}'.format(resp.status_code))
            return None
        root = document_fromstring(resp.text)
        if taskItems and taskItems.trim:
            trim_chapter(root)
        with open(html_name, 'wb') as f:
            f.write(tostring(root))
        convert_args = ['ebook-convert', html_name, epub_name, '--no-default-epub-cover']
        print(' '.join(map(quote_arg, convert_args)))
        res = subprocess.run(convert_args, stdout=subprocess.DEVNULL)
        if res.returncode != 0:
            return None
        return epub_name
    
    #cleanup temp files
    finally:
        try:
            os.remove(html_name)
        except:
            pass

def process_volume(url, taskItems: TaskItems =None):
    assert(url)
    base_url = '/'.join(url.split('/')[:-1]) + '/'
    print('downloading {}'.format(url))
    resp = requests.get(url)
    if resp.status_code != 200:
        if resp.status_code == 404:
            print('received 404, skipping {}'.format(url))
            if taskItems:
                taskItems.errors404.put(url)
        print('received error code {}'.format(resp.status_code))
        return None
    root = document_fromstring(resp.text)
    anchors = root.xpath('//a')
    chapter_urls = []
    for a in anchors:
        href = a.get('href')
        if href is None:
            continue
        if '/' in href or '#' in href:
            continue
        if not (href.endswith('.htm') or href.endswith('.html')):
            continue
        chapter_urls.append(href)
    chapter_names = []
    try:
        for chapter_url in chapter_urls:
            ch = process_chapter(base_url + chapter_url, taskItems)
            if ch is None:
                return None
            #empty strings mean an intentionally skipped chapter
            if ch == '':
                continue
            chapter_names.append(ch)
        if not chapter_names:
            return ''
        vol_name = rand_name() + '.epub'
        merge_args = ['calibre-debug', '--run-plugin', 'EpubMerge', '--',
            '-N', '-o', vol_name] + chapter_names
        print(' '.join(map(quote_arg, merge_args)))
        res = subprocess.run(merge_args, stdout=subprocess.DEVNULL)
        if res.returncode:
            return None
        return vol_name
    #cleanup temp files
    finally:
        for ch in chapter_names:
            try:
                os.remove(ch)
            except:
                pass

def main(cli_args):
    parser = ArgumentParser()
    parser.add_argument('-o', '--output', help='output file name', type=str)
    parser.add_argument('-t', '--title', help='ebook title', type=str)
    parser.add_argument('-a', '--author', help="ebook author", type=str, action='append')
    parser.add_argument('-g', '--tag', help='apply a tag', action='append')
    parser.add_argument('-r', '--rating', help='set the rating', type=int, default=None, choices=range(1,6), metavar='[1-5]')
    parser.add_argument('-I', '--images', help='NOT IMPLEMENTED also attempt to download any images', action='store_true')
    parser.add_argument('-C', '--auto-cover', help='NOT IMPLEMENTED generate an automatic cover', action='store_true', dest='cover')
    parser.add_argument('-T', '--no-trim', help="don't try to trim footer at bottom of chapters", action='store_false', dest='trim')
    #TODO add arguments to control ToC
    parser.add_argument('url', help='url to download', nargs='+')
    #args = parser.parse_args(cli_args)
    args = parser.parse_args()
    urls = args.url
    name = args.output or 'output.epub'
    title = args.title
    authors = args.author
    tags = args.tag
    store_images = args.images
    cover = args.cover
    trim = args.trim
    rating = args.rating
    taskItems = TaskItems(errors404=SimpleQueue(), store_images=store_images,
        trim=trim)
    #TODO clearer variable names
    documents = []
    docs = []
    with ThreadPoolExecutor() as executor:
        try:
            for item in urls:
                if 'index' in item:
                    documents.append(executor.submit(process_volume, url=item, taskItems=taskItems))
                else:
                    documents.append(executor.submit(process_chapter, url=item, taskItems=taskItems))
            try:
                concurrent.futures.wait(documents, timeout=10*60)
            except concurrent.futures.TimeoutError:
                print('Timeout while waiting for tasks')
                return 1
            docs = [d.result() for d in documents]
            docs = [d for d in docs if d]
            #epub[] => epub
            if cover or not name.endswith('.epub'):
                merge_name = rand_name() + '.epub'
            else:
                #no final conversion step
                merge_name = name
            merge_args = ['calibre-debug', '--run-plugin', 'EpubMerge', '--',
                '-o', merge_name]
            merge_args += docs
            print(' '.join(map(quote_arg, merge_args)))
            res = subprocess.run(merge_args, stdout=subprocess.DEVNULL)
            if res.returncode:
                print('final merge failed')
                return 1
            if name != merge_name:
                try:
                    #epub => output type
                    convert_args = ['ebook-convert', merge_name, name]
                    if authors:
                        convert_args += ['--authors', '&'.join(authors)]
                    if title:
                        convert_args += ['--title', title]
                    if tags:
                        convert_args += ['--tags', ','.join(tags)]
                    if rating:
                        convert_args += ['--rating', str(rating)]
                    print(' '.join(map(quote_arg, convert_args)))
                    res = subprocess.run(convert_args, stdout=subprocess.DEVNULL)
                    if res.returncode:
                        print('final conversion failed')
                        return res.returncode
                finally:
                    try:
                        os.remove(merge_name)
                    except:
                        pass
            return 0
        #cleanup temp files
        finally:
            try:
                while True:
                    print('received 404: {}'.format(taskItems.errors404.get(False)))
            except Empty:
                pass
            for item in docs:
                try:
                    os.remove(item)
                except:
                    pass

if __name__ == '__main__':
    exit(main(argv[1:]))

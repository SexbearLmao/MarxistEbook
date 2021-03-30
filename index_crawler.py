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
    def __init__(self, errors404: SimpleQueue, store_images: bool =False):
        self.errors404 = errors404
        self.store_images = store_images

def rand_name():
    return '%030x' % random.randrange(16**30)

def clip_chapter(root):
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
        clip_chapter(root)
        with open(html_name, 'wb') as f:
            f.write(tostring(root))
        convert_args = ['ebook-convert', html_name, epub_name, '--no-default-epub-cover']
        print(' '.join(convert_args))
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
        print(' '.join(merge_args))
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
    parser.add_argument('-a', '--author', help='ebook author', type=str)
    parser.add_argument('-g', '--tag', help='apply a tag', action='append')
    parser.add_argument('-I', '--images', help='also attempt to download any images', action='store_true')
    parser.add_argument('-C', '--auto-cover', help='generate an automatic cover', action='store_true', dest='cover')
    parser.add_argument('url', help='url to download', nargs='+')
    #args = parser.parse_args(cli_args)
    args = parser.parse_args()
    urls = args.url
    name = args.output or 'output.epub'
    title = args.title
    author = args.author
    tags = args.tag
    store_images = args.images
    cover = args.cover
    taskItems = TaskItems(errors404=SimpleQueue(), store_images=store_images)
    documents = []
    with ThreadPoolExecutor() as executor:
        try:
            for item in urls:
                if 'index' in item:
                    documents.append(executor.submit(process_volume, url=item, taskItems=taskItems))
                else:
                    documents.append(executor.submit(process_chapter, url=item, taskItems=taskItems))
            concurrent.futures.wait(documents, timeout=10*60)
            docs = [d.result() for d in documents]
            docs = [d for d in docs if d]
            merge_name = name if name.endswith('.epub') else (rand_name() + '.epub')
            merge_args = ['calibre-debug', '--run-plugin', 'EpubMerge', '--',
                '-N', '-o', merge_name]
            if title:
                merge_args += ['-t', title]
            if author:
                merge_args += ['-a', author]
            for tag in tags:
                merge_args += ['-g', tag]
            merge_args += docs
            print(' '.join(merge_args))
            res = subprocess.run(merge_args, stdout=subprocess.DEVNULL)
            if res.returncode:
                print('final merge failed')
                return 1
            if name != merge_name:
                try:
                    convert_args = ['ebook-convert', merge_name, name]
                    print(' '.join(convert_args))
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

from lxml.html import tostring, document_fromstring
from argparse import ArgumentParser
import requests
import random
import subprocess
import os
from multiprocessing import Pool

def rand_name():
    return '%030x' % random.randrange(16**30)

def download_chapter(url):
    print('downloading {}'.format(url))
    response = requests.get(url)
    if response.status_code != 200:
        #TODO find correct exception
        raise Exception('failed to download page')
    root = document_fromstring(response.text)

    #find and remove footer
    comments = root.xpath('//comment()')
    foot = next(filter(lambda e: 't2h-foot ' in e.text, comments))
    parent = foot.getparent()
    prev = foot.getprevious()
    while prev.getnext()is not None:
        parent.remove(prev.getnext())
    
    randname = rand_name()
    htmlname = randname + '.html'
    epubname = randname + '.epub'
    with open(htmlname, 'wb') as f:
        f.write(tostring(root))
    
    convert_args = ['ebook-convert', htmlname, epubname, '--no-default-epub-cover']
    print(' '.join(convert_args))
    comp = subprocess.run(convert_args, stdout=subprocess.DEVNULL)
    if comp.returncode:
        #TODO find correct exception
        raise Exception('subprocess returned error code {}'.format(comp.returncode))
    os.remove(htmlname)
    return epubname

def download_book(url):
    response = requests.get(url)
    if response.status_code != 200:
        print('failed to download page')
        exit(1)
    root = document_fromstring(response.text)

    #I think this finds multi-page docs
    spans = root.xpath('//span')
    toc = None
    try:
        toc = next(filter(lambda e: 'toc' in e.classes, spans))
    except StopIteration:
        pass
    if toc is None:
        #TODO this will download page a second time, allow passing text directly
        return download_chapter(url)
    else:
        #TODO make better
        title = [e for e in root.xpath('//h3') if 'title' in e.classes][0].text

        base_path = '/'.join(url.split('/')[:-1])
        spans = root.xpath('//span')
        spans = filter(lambda e: 'toc' in e.classes, spans)
        def get_link(s):
            return base_path + '/' + s.xpath('a')[0].get('href')
        links = [get_link(s) for s in spans]
        with Pool() as pool:
            res = pool.map(download_chapter, links)
        temp_name = rand_name() + '.epub'
        merge_args = ['calibre-debug', '--run-plugin', 'EpubMerge', '--',
            '-N', '-o', temp_name, '-t', title] + res
        print(' '.join(merge_args))
        sub = subprocess.run(merge_args, stdout=subprocess.DEVNULL)
        if sub.returncode:
            #TODO correct exception
            raise Exception('merge returned {}'.format(sub.returncode))
        #cleanup temporary files
        for f in res:
            os.remove(f)
        return temp_name
        

def main():
    parser = ArgumentParser()
    parser.add_argument('-o', '--output', help='name of output file', dest='output')
    parser.add_argument('-i', '--input', help='input urls', dest='input', action='append')
    #parser.add_argument('-e', '--executable', help='directory of calibre executables', dest='exec')
    parser.add_argument('-t', '--title', help='set the title manually', dest='title', default=None)
    parser.add_argument('-a', '--author', help='set the author manually', dest='author', default=None)
    args = parser.parse_args()
    inp = args.input
    outp = args.output or 'output.epub'
   # exec_dir = args.exec
    title = args.title
    author = args.author


    output_extension = os.path.split(outp)[1]

    books = [download_book(i) for i in inp]
    if len(books) > 1:
        temp_name = rand_name() + '.epub'
        merge_args = ['calibre-debug', '--run-plugin', 'EpubMerge', '--',
            '-N', '-o', temp_name]
        if title is not None:
            merge_args += ['-t', title]
        if author is not None:
            merge_args += ['-a', author]
        merge_args += books
        sub = subprocess.run(merge_args, stdout=subprocess.DEVNULL)
        if sub.returncode:
            #TODO correct exception
            raise Exception('final merge returned {}'.format(sub.returncode))
        for book in books:
            os.remove(book)

    if output_extension == '.epub':
        os.rename(temp_name, outp)
    else:
        sub = subprocess.run(['ebook-convert', temp_name, outp], stdout=subprocess.DEVNULL)
        if sub.returncode:
            #TODO correct exception
            raise Exception('final conversion returned {}'.format(sub.returncode))
        os.remove(temp_name)
    print('created {}'.format(outp))

if __name__ == '__main__':
    main()

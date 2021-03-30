from lxml.html import tostring, document_fromstring
from argparse import ArgumentParser
import requests
import random
import subprocess
import os
from sys import argv
from multiprocessing import Pool

def rand_name():
    return '%030x' % random.randrange(16**30)

def all_children(node):
    for child in node.getchildren():
        for item in all_children(child):
            yield item
        yield child
    yield node

def download_chapter(url):
    print('downloading {}'.format(url))
    response = requests.get(url)
    if response.status_code != 200:
        #TODO find correct exception
        raise Exception('failed to download page')
    root = document_fromstring(response.text)

    #find and remove footer
    try:
        comments = root.xpath('//comment()')
        foot = next(filter(lambda e: 't2h-foot ' in e.text, comments))
        parent = foot.getparent()
        prev = foot.getprevious()
        while prev.getnext() is not None:
            parent.remove(prev.getnext())
    except StopIteration:
        pass
    
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
        #this shouldn't exit
        exit(1)
    root = document_fromstring(response.text)

    #I think this finds multi-page docs
    tocs = [node for node in all_children(root) if 'toc' in node.classes]
    
    if tocs:
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
    else:
        #TODO this will download page a second time, allow passing text directly
        return download_chapter(url)
    else:
        
        

def main(cli_args):
    parser = ArgumentParser()
    parser.add_argument('-o', '--output', help='name of output file', dest='output')
    #parser.add_argument('-i', '--input', help='input urls', dest='input', action='append')
    #parser.add_argument('-e', '--executable', help='directory of calibre executables', dest='exec')
    parser.add_argument('-t', '--title', help='set the title manually', dest='title', default=None)
    parser.add_argument('-a', '--author', help='set the author manually', dest='author', default=None)
    parser.add_argument('-d', '--description', help='set the book descripton', default=None)
    parser.add_argument('-g', '--tag', help='apply a tag', action='append')
    parser.add_argument('-l', '--language', help='set language', default=None)
    parser.add_argument('url', help='urls to download', nargs='+')
    args = parser.parse_args(cli_args)
    #inp = args.input
    urls = args.url
    outp = args.output or 'output.epub'
    #exec_dir = args.exec
    title = args.title
    author = args.author
    description = args.description
    tags = args.tag
    lanugage = args.language

    for i in range(len(urls)-1):
        if urls[i] in urls[i+1:]:
            print('duplicate url:')
            print(urls[i])
            return 1

    output_extension = os.path.split(outp)[1]

    books = [download_book(i) for i in urls]
    if len(books) > 1:
        temp_name = rand_name() + '.epub'
        merge_args = ['calibre-debug', '--run-plugin', 'EpubMerge', '--',
            '-N', '-o', temp_name]
        if title is not None:
            merge_args += ['-t', title]
        if author is not None:
            merge_args += ['-a', author]
        for t in tags:
            merge_args += ['-g', t]
        if description is not None:
            merge_args += ['-d', description]
        if lanugage is not None:
            merge_args += ['-l', lanugage]
        merge_args += books
        sub = subprocess.run(merge_args, stdout=subprocess.DEVNULL)
        if sub.returncode:
            #TODO correct exception
            raise Exception('final merge returned {}'.format(sub.returncode))
        for book in books:
            os.remove(book)
    else:
        #select the single item as the merge result
        #TODO apply metadata
        temp_name = books[0]

    if output_extension == '.epub':
        os.rename(temp_name, outp)
    else:
        sub = subprocess.run(['ebook-convert', temp_name, outp], stdout=subprocess.DEVNULL)
        if sub.returncode:
            #TODO correct exception
            raise Exception('final conversion returned {}'.format(sub.returncode))
        os.remove(temp_name)
    print('created {}'.format(outp))
    return 0

if __name__ == '__main__':
    exit(main(argv))

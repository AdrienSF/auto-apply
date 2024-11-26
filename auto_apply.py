import datetime
import os
import json
from collections import Counter
from copy import deepcopy
import time

from selenium import webdriver
import selenium
from bs4 import BeautifulSoup
import bs4
from selenium.webdriver.common.by import By
import jsonlines as jsonl
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from scipy.optimize import linear_sum_assignment
from sentence_transformers import SentenceTransformer

from utils import datetime_parser, datetime_serializer


places = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth']
text_types = ['text', 'email', "date", "datetime-local", "month", "number", "password", "search", "tel", "time", "url", "week"] # not sure all of these are really considered text, might break send_keys()
xforbid = ['$', '{', '}']

class AutoApply():
    '''
    Interacts with indeed and aplication portals, 
    employs semantic search to find appropriate (preset) answers used to auto-fill forms
    '''

    def __init__(
        self,
        folder_name='file_templates/'
    ) -> None:
        self.folder_name = folder_name
        self.search_url_filename = 'search_urls.txt'
        with open(self.folder_name+self.search_url_filename) as f:
            self.search_urls = f.read().split('\n')
        self.seen_jobs_filename = 'seen_jobs.jsonl'
        self.applied_jobs_filename = 'applied_jobs.jsonl'
        self.scraped_jobs_filename = 'scraped_jobs.jsonl'
        self.recency_timedelta = datetime.timedelta(days=30)
        self.max_context_size = 256
        self.close_context_size = 64
        self.form_element_similarity_thresh = .98
        self.element_sim_thresh = .1
        self.context_sim_thresh = .3
        self.informative_input_el_attrs = {'id', 'name', 'value', 'placeholder'}
        self.sbert = SentenceTransformer("multi-qa-mpnet-base-cos-v1")

        self.form_answers_filename = 'form_answers.json'
        self.load_answers()

        # this workaround can help convince cloudflare and others that you are a real human
        os.system('google-chrome https://www.indeed.com/ -remote-debugging-port=9014 -user-data-dir='+self.folder_name+'.chromeData &')
        input('log into Indeed (if necessary) and press [enter] to continue: ')
        options = webdriver.ChromeOptions()
        options.add_experimental_option('debuggerAddress', 'localhost:9014')
        self.driver = webdriver.Chrome(options=options)

    def load_answers(self):
        '''reload form answers'''
        with open(self.folder_name+self.form_answers_filename) as f:
            self.form_keys, self.form_answers = zip(*json.load(f).items())
            self.form_key_embs = self.sbert.encode(self.form_keys)

    def get_page(self, url: str):
        '''
        return BeautifulSoup of the page's html, obtained through selenium

        Parameters
        ----------
        url : str
            url of the page to get

        Returns
        -------
        BeautifulSoup
            BeautifulSoup of the page's html
        '''
        self.driver.get(url)
        return BeautifulSoup(self.driver.page_source, 'html.parser')

    def get_description_urls(self, search_page: BeautifulSoup):
        '''
        return urls to job description pages of every result of an indeed search result page

        Parameters
        ----------
        search_page : BeautifulSoup
            the indeed search results page from which to extract job description links

        Returns
        -------
        list
            urls that bring you to job description pages
        '''
        titles = search_page.find_all(class_='jcs-JobTitle')
        return ['https://www.indeed.com'+t['href'] for t in titles]

    def get_description(self, description_page: BeautifulSoup):
        '''
        return the job description text from it's webpage

        Parameters
        ----------
        description_page : BeautifulSoup
            a job description page

        Returns
        -------
        str
            job description text
        '''
        return description_page.find(id='jobDescriptionText').get_text()

    def get_indeed_apply_url(self, description_page: BeautifulSoup):
        '''
        return indeed's url to apply to the job on the given job description page

        Parameters
        ----------
        description_page : BeautifulSoup
            a job description page

        Returns
        -------
        str
            application url
        '''

        link_container = description_page.find(id='applyButtonLinkContainer')
        if link_container:
            return link_container.find('button')['href']
        else: # could not find link
            return None
        
    def load_jobs(self):
        '''
        Load previously scraped jobs

        Returns
        -------
        list of dicts
            each dict corresponds to one job with:
            - apply_url: str
                link to company's application portal 
            - description: str
                job escription
            - date_scraped: datetime.datetime
                date of the dict's creation
            - search_url: str
                the urls of the search results page in which this job was found
        '''
        with jsonl.open(self.folder_name+self.scraped_jobs_filename) as f:
            return [datetime_parser(e) for e in f]

    def get_jobs(self, search_urls: list[str]=None, delay=1):
        '''
        get the job description text and application portal url from the first page of search results 
        of a list of indeed searches

        Parameters
        ----------
        search_urls : list[str], default None
            list of indeed search urls. If None, uses self.search_urls which is loaded from self.search_url_filename

        Returns
        -------
        list of dicts
            each dict corresponds to one job with:
            - apply_url: str
                link to company's application portal 
            - description: str
                job escription
            - date_scraped: datetime.datetime
                date of the dict's creation
            - search_url: str
                the urls of the search results page in which this job was found
        '''
        
        if search_urls==None:
            search_urls = self.search_urls
        scrape = {search_url: {'search_page': self.get_page(search_url)} for search_url in search_urls}
        for search_url in scrape:
            time.sleep(delay)
            scrape[search_url]['description_page_urls'] = self.get_description_urls(scrape[search_url]['search_page'])
            scrape[search_url]['description_pages'] = [self.get_page(url) for url in scrape[search_url]['description_page_urls']]

        jobs = []
        for search_url in scrape:
            for page, url in zip(scrape[search_url]['description_pages'], scrape[search_url]['description_page_urls']):
                time.sleep(delay)
                description = self.get_description(page)
                indeed_joblink_redirect = self.get_indeed_apply_url(page)
                if not indeed_joblink_redirect: # if the link was not found, just use the indeed description page url
                    indeed_joblink_redirect = url
                self.driver.get(indeed_joblink_redirect)
                apply_url = self.driver.current_url

                j = {'search_url': search_url, 'apply_url': apply_url, 'description': description, 'date_scraped': datetime.datetime.now()}
                jobs.append(j)
                # save scraped jobs to a file. don't want to repeatedly scrape the same jobs or indeed will block
                with jsonl.open(self.folder_name+self.scraped_jobs_filename, 'a') as f:
                    f.write(datetime_serializer(j))

        return jobs
    
    def view_jobs(self, jobs: list[dict]):
        '''
        display job pages, record which jobs were viewed

        Parameters
        ----------
        jobs : list of dicts
            the jobs to view, should have the structure of the output of get_jobs()

        Returns
        -------
        list of dicts
            jobs that have been viewed, with the date viewed
        '''
        seen = []
        for job in jobs:
            self.driver.get(job['apply_url'])
            job['date_seen'] = datetime.datetime.now()
            seen.append(job)
            with jsonl.open(self.folder_name+self.seen_jobs_filename, 'a') as f:
                f.write(datetime_serializer(job))
            if input('[enter] to view next job, anything else to stop viewing'):
                break
        return deepcopy(seen)

    def filter_jobs(self, jobs: list[dict]):
        '''
        return only the jobs that fit certain criteria: haven't been seen recently (that's it for now)

        Parameters
        ----------
        jobs : list of dicts
            the jobs to filter, should have the structure of the output of get_jobs()

        Returns
        -------
        list of dicts
            jobs that pass the filter       
        '''
        # remove jobs that have been seen recently
        with jsonl.open(self.folder_name+self.seen_jobs_filename) as f:
            recently_seen = [datetime_parser(job) for job in f if datetime_parser(job)['date_seen'] > datetime.datetime.now() - self.recency_timedelta]

        fresh_jobs = pd.DataFrame(jobs+recently_seen).drop_duplicates('description', keep=False).to_dict('records')

        # filter jobs based on any other requirements
        filtered_jobs = fresh_jobs # nothing for now

        return filtered_jobs

    def get_form_elements_html(self, form_page: BeautifulSoup):
        '''
        return list of all form elements in bs4 page

            Parameters
            ----------
            form_page : BeautifulSoup
                the bs4 page with form elements

            Returns
            -------
            list of bs4.element.Tag
                all the bs4 form elements present in the input page

        '''        
        form_el_names = ['input', 'select', 'textarea', 'datalist',  'optgroup'] # removed 'button'
        form_els = []
        for el in form_el_names:
            form_els += form_page.find_all(el)
        return form_els

    def get_query_from_html(self, html_el: bs4.element.Tag):
        '''
        return all the attributes of an element in the format required for document.querySelector().

            Parameters
            ----------
            html_el : bs4.element.Tag
                the bs4 element we want to find an equivalent js query for

            Returns
            -------
            str
                query string for document.querySelector()

        '''        
        return ''.join([ '['+attr+'=\"'+val+'\"]' for attr, vals in [(a, v if type(v)==list else [v]) for a, v in html_el.attrs.items()] for val in vals ])
    
    def get_xpath_from_html(self, html_el: bs4.element.Tag, use_text=False):
        '''
        return all the attributes of an element in xpath format required for selenium driver.find_elements()

            Parameters
            ----------
            html_el : bs4.element.Tag
                the bs4 element we want to find an equivalent xpath for
            use_text : bool, default False
                wether or not to include the inner text of the element in the xpath

            Returns
            -------
            str
                xpath for driver.find_elements(By.XPATH, xpath)

        '''      
        def enquote(s):
            s = str(s)
            # big problem for xpath if both types of quotes in s... there is no solution
            if "'" in s:
                return '"' + s + '"'
            else:
                return "'" + s + "'"


        selectors= []
        for k, l in html_el.attrs.items():
            if type(l)== list:
                # xpath can't handle these chars
                if any(any(f in e for e in l) for f in xforbid):
                    continue
                # selectors.append('('+' or '.join(['@'+k+'='+enquote(v) for v in l])+')')
                selectors.append('@'+k+'='+enquote(' '.join(l)))
            else:
                if any(f in l for f in xforbid):
                    continue
                selectors.append('@'+k+'='+enquote(l))
        # add inner text as selector
        if use_text and html_el.text:
            selectors.append('text()='+enquote(html_el.text))
        xpath = '//'+html_el.name+'[' + ' and '.join(selectors) + ']'
        return xpath

    def get_surrounding_text(self, html_el: bs4.element.Tag, thresh=float):
        '''
        return text of the furthest grandparent with text no greater than self.max+context_size characters

            Parameters
            ----------
            html_el : bs4.element.Tag
                bs4 element to get the surrounding text of

            Returns
            -------
            str
                text of the furthest grandparent with text no greater than self.max+context_size characters

        '''        
        # exclude options from surrounding text: these represent an answer not the question so they will not semantically match well with the form_answer.json keys
        def get_filtered_text(el: bs4.element.Tag, blacklist=['option']):
            text = el.get_text()
            for bl in blacklist:
                for child in el.find_all(bl):
                    text = text.replace(child.get_text(), '')

            return text
        
        while len(get_filtered_text(html_el.parent)) <= thresh:
            html_el = html_el.parent

        return get_filtered_text(html_el)
    
    def describe_element(self, html_el: bs4.element.Tag):
        '''
        extracts text directly surrounding the input form element, as well as useful attributes of the element that may be descriptive of it's purpose

            Parameters
            ----------
            html_el : bs4.element.Tag
                bs4 element to describe

            Returns
            -------
            str
                surrounding text + self.informative_input_el_attrs
        '''
        usefull_attrs = {k: v for k, v in html_el.attrs.items() if k in self.informative_input_el_attrs}
        return self.get_surrounding_text(html_el, self.close_context_size) + ' ' + str(usefull_attrs)

    def get_form_answers(self, contexts: list[str], form_els: list[str]):
        '''
        semantic search pre-set form answers based on form element and it's context

            Parameters
            ----------
            contexts : list[str]
                list of string of context to inform the semantic search
            form_els : list[str]
                list of string of the form element itself, also to inform the semantic search

            Returns
            -------
            str
                best of the pre-set form answers to fill the form element with

        '''        
        def strip_unks(strings): # remove characters unknown to sbert
            return [''.join([c for c in s if self.sbert.tokenizer(c)['input_ids'][1] != 104]) for s in strings]
        
        context_embs = self.sbert.encode(strip_unks(contexts))
        el_embs = self.sbert.encode(strip_unks(form_els))
        co_sims, el_sims = cosine_similarity(context_embs, self.form_key_embs), cosine_similarity(el_embs, self.form_key_embs)
        similarities = co_sims + el_sims
        # get most similar pairs
        answer_indexes = linear_sum_assignment(similarities, maximize=True)[1]
        # ignore fields with bad match on context OR element
        to_ignore = [co_sims[i, answer_indexes[i]] < self.context_sim_thresh or el_sims[i, answer_indexes[i]] < self.element_sim_thresh for i in range(len(answer_indexes))] 
        return [self.form_answers[k] if not to_ignore[i] else '' for i, k in enumerate(answer_indexes)]

    def get_best_option(self, options: list[bs4.element.Tag], context: str, form_el: str):
        '''
        semantic search pre-set form answers based on form element and it's context

            Parameters
            ----------
            options : list[bs4.element.Tag]
                list of options to choose from
            context : str
                string of context to inform the semantic search
            form_el : str
                string of the form element itself, also to inform the semantic search

            Returns
            -------
            bs4.element.Tag
                closest matching option found

        '''        
        # get answer to context and form el
        ans = self.get_form_answers([context], [form_el])[0]
        # find option closely matching answer
        option_embs = self.sbert.encode([e.get_text() for e in options])
        sims = cosine_similarity(self.sbert.encode([ans]), option_embs)
        best_opt_i = sims.argmax()

        return options[best_opt_i]


    def get_duplicate_element_indexes(self, elements: list[bs4.element.Tag]):
        '''
        finds duplicates in a list of bs4 elements, returns their indexes

            Parameters
            ----------
            elements : list[bs4.element.Tag]
                bs4 elements to check for duplicates

            Returns
            -------
            list[list[int]]
                lists of duplicate's indexes, each list contains indexes of identical elements

        '''        
        el_attrs_list = [frozenset((a, tuple(v) if type(v)==list else v) for a, v in el.attrs.items()) for el in elements]
        return [[i for i, el in enumerate(el_attrs_list) if el == d] for d, c in Counter(el_attrs_list).items() if c>1]

    def autofill_current_page(self, delay=.1):
        '''fill any form elements on the driver's active page with preset answers'''
        def try_find_element(el: bs4.element.Tag):
            # first try to get by ID only
            if 'id' in el.attrs:
                drels = self.driver.find_elements(By.ID, el['id'])
                if len(drels) == 1:
                    return drels
            # if it's an option, we need to specify the parent and text value
            if el.name == 'option':
                try:
                    drels = self.driver.find_elements(By.XPATH, self.get_xpath_from_html(el.parent) + self.get_xpath_from_html(el, True))
                    if len(drels) > 1:
                        print('Warning: found multiple elements matching:', el, 'with text:', el.text)
                    elif len(drels) < 1:
                        print('Warning: found no elements matching:', el, 'with text:', el.text)
                    return drels
                except selenium.common.exceptions.InvalidSelectorException as e:
                    print('Warning: could not make valid selector for element:', el, 'with text:', el.text)
                    return []
            else: # if not an option, we need not specify the parent or text value (that could complicate things: what if no text value? what if parent has xforbidden chars?)
                try:
                    drels = self.driver.find_elements(By.XPATH, self.get_xpath_from_html(el))
                    if len(drels) > 1:
                        print('Warning: found multiple elements matching:', el)
                    elif len(drels) < 1:
                        print('Warning: found no elements matching:', el)
                    return drels
                except selenium.common.exceptions.InvalidSelectorException as e:
                    print('Warning: could not make valid selector for element:', el)
                    return []

        def fill_text(text_els: list[bs4.element.Tag]):
            # deal with duplicates
            dupe_idxs = self.get_duplicate_element_indexes(text_els)
            # map elements to answers
            # make queries
            el_strings = []
            for idx, el in enumerate(text_els):
                if any(idx in dis for dis in dupe_idxs):
                    i = [dis.index(idx) for dis in dupe_idxs if idx in dis][0] # el is the i'th duplicate
                    # enrich query with position
                    el_str = places[i]+' '+self.describe_element(el)
                else:
                    el_str = self.describe_element(el)
                el_strings.append(el_str)
                contexts = [self.get_surrounding_text(el, self.max_context_size) for el in text_els]

            form_answers = self.get_form_answers(contexts, el_strings)
            # input answers
            for idx in range(len(text_els)):
                if any(idx in dis for dis in dupe_idxs):
                    i = [dis.index(idx) for dis in dupe_idxs if idx in dis][0] # el is the i'th duplicate
                else:
                    i = 0
                el = text_els[idx]
                to_input = form_answers[idx]
                driver_els = try_find_element(el) # might not find anything and return []
                if driver_els and not driver_els[i].get_attribute('value'): # only input if no text already input
                    time.sleep(delay)
                    driver_els[i].send_keys(to_input)



        form_page = BeautifulSoup(self.driver.page_source, 'html.parser')
        all_form_els = self.get_form_elements_html(form_page)
        # remove fake elements the user can't see or use
        # form_els = [ el for el in form_els if all(d_el.is_displayed() and d_el.is_enabled() for d_el in self.driver.find_elements(By.XPATH, self.get_xpath_from_html(el)))]
        filtered_form_els = []
        for el in all_form_els:
            if all(d_el.is_displayed() and d_el.is_enabled() for d_el in try_find_element(el)):
                filtered_form_els.append(el)


        # handle dropdown selection
        click_form_els = [el for el in filtered_form_els if any(subel.name=='option' for subel in el.children)]
        for el in click_form_els:
            options = [e for e in el.children if e.name=='option']
            opt = self.get_best_option(options, self.get_surrounding_text(el, self.max_context_size), self.describe_element(el))
            driver_els = try_find_element(opt)
            for drel in driver_els:
                time.sleep(delay)
                drel.click()


        # handle text answers
        form_els = [el for el in filtered_form_els if (el.name == 'input' and ('type' in el.attrs) and any(t in el['type'] for t in text_types)) or el.name == 'textarea']
        if form_els:
            fill_text(form_els)


        # handle other inputs of unknown purpose
        other_els = [el for el in filtered_form_els if el not in form_els]
        if other_els:
            try:
                fill_text(other_els)
            except Exception as e:
                print('Warning: filling unknown inputs resulted in:')
                print(e)



    def log_applied(self, jobs: list[dict]):
        '''
        Save jobs to self.folder_name+self.applied_jobs_filename

            Parameters
            ----------
            jobs : list[dict]
                jobs to save as applied

            Returns
            -------
            None

        ''' 

        for job in jobs:
            job['date_applied'] = datetime.datetime.now()
        with jsonl.open(self.folder_name+self.applied_jobs_filename, 'a') as f:
            f.write_all([datetime_serializer(j) for j in jobs])

    def close(self):
        '''close selenium driver'''
        self.driver.close()

    def scrape_job(self, url, delay=1):
        '''
        Save job page info to self.folder_name+self.scraped_jobs_filename

            Parameters
            ----------
            url : str
                url of the page to scrape
            delay : float
                time in seconds to wait before repeat call

            Returns
            -------
            job: dict

        '''  

        time.sleep(delay)
        self.driver.get(url)
        j = {'search_url': None, 'apply_url': self.driver.current_url, 'description': BeautifulSoup(self.driver.page_source, 'html.parser').get_text(), 'date_scraped': datetime.datetime.now()}
        # save scraped jobs to a file. don't want to repeatedly scrape the same jobs or indeed will block
        with jsonl.open(self.folder_name+self.scraped_jobs_filename, 'a') as f:
            f.write(datetime_serializer(j))
        return j
# auto-apply
It seems most of the time spent applying to jobs is taken by the tedious filling of endless forms. While some application portals offer to fill forms from a resume or LinkedIn profile, this feature is unfortunately quite rare and often doesn't work very well... so I've implemented it myself. I originally used ChatGPT, but I later optimized my pipeline to run locally on any laptop, using over 5000x less memory for the same result. This project now uses [sBERT](https://sbert.net/) language model to find appropriate answers to forms, and fill them automatically.


There are still many types of HTML form elements this project doesn't know how to handle, but at this rate I will spend more time on this project than on actual applications, so I don't expect to continue working on it. (Feel free to fork and improve it yourself)

## How it works
I use [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/) to extract text directly next to form input elements (e.g. 'Enter full name:'), as well as the wider context around inputs (e.g. 'Form 1: personal information). sBERT allows me to get a similarity score between this text and preset form answers; after linear sum assignment each form element is assigned the most appropriate answer. [Selenium](https://pypi.org/project/selenium/) is then used to input the answers into the form.

## How to use
### dependencies
This project uses the following packages for python 3.10.12:

```pip3 install selenium bs4 jsonlines pandas scikit-learn scipy sentence_transformers```

Chrome is also required for Selenium to work.

### Form answers
Form answers are stored as a non-nested dict, where each key is matched to text around a form element, and values are input as answers. For best results, the keys should incorporate multiple ways a form question might be commonly formulated (ex: 'surname / last name'), including contextual info such as the form section/title (ex: 'Personal info'). When there are multiple near-identical entries, numbers should be added to the keys to distinguish them (ex: 'First job experience', 'second job experience') ```file_templates/form_answers.json``` shows what this looks like for my use case.

### Basic usage
To use, initialise an AutoApply object and specify the directory containing ```form_answers.json```. After this opens Chrome with selenium, navigate to a form page and call ```autofill_current_page()```
```python
from auto_apply import AutoApply
auto_app = AutoApply(folder_name='file_templates')
auto_app.autofill_current_page()
```

```auto_apply.ipynb```  shows examples of how to do this as well as all other features such as saving job descriptions, scraping indeed, and keeping track of which jobs have already been seen.

# Documentation
Generated from docstrings using [this](https://stackoverflow.com/questions/36237477/python-docstrings-to-github-readme-md), formatting may be a bit inconsistent.


* [auto_apply module](auto_apply.md)
  * [`AutoApply`](auto_apply.md#auto_apply.AutoApply)
    * [`AutoApply.__init__()`](auto_apply.md#auto_apply.AutoApply.__init__)
    * [`AutoApply.autofill_current_page()`](auto_apply.md#auto_apply.AutoApply.autofill_current_page)
    * [`AutoApply.close()`](auto_apply.md#auto_apply.AutoApply.close)
    * [`AutoApply.describe_element()`](auto_apply.md#auto_apply.AutoApply.describe_element)
    * [`AutoApply.filter_jobs()`](auto_apply.md#auto_apply.AutoApply.filter_jobs)
    * [`AutoApply.get_best_option()`](auto_apply.md#auto_apply.AutoApply.get_best_option)
    * [`AutoApply.get_description()`](auto_apply.md#auto_apply.AutoApply.get_description)
    * [`AutoApply.get_description_urls()`](auto_apply.md#auto_apply.AutoApply.get_description_urls)
    * [`AutoApply.get_duplicate_element_indexes()`](auto_apply.md#auto_apply.AutoApply.get_duplicate_element_indexes)
    * [`AutoApply.get_form_answers()`](auto_apply.md#auto_apply.AutoApply.get_form_answers)
    * [`AutoApply.get_form_elements_html()`](auto_apply.md#auto_apply.AutoApply.get_form_elements_html)
    * [`AutoApply.get_indeed_apply_url()`](auto_apply.md#auto_apply.AutoApply.get_indeed_apply_url)
    * [`AutoApply.get_jobs()`](auto_apply.md#auto_apply.AutoApply.get_jobs)
    * [`AutoApply.get_page()`](auto_apply.md#auto_apply.AutoApply.get_page)
    * [`AutoApply.get_query_from_html()`](auto_apply.md#auto_apply.AutoApply.get_query_from_html)
    * [`AutoApply.get_surrounding_text()`](auto_apply.md#auto_apply.AutoApply.get_surrounding_text)
    * [`AutoApply.get_xpath_from_html()`](auto_apply.md#auto_apply.AutoApply.get_xpath_from_html)
    * [`AutoApply.load_answers()`](auto_apply.md#auto_apply.AutoApply.load_answers)
    * [`AutoApply.load_jobs()`](auto_apply.md#auto_apply.AutoApply.load_jobs)
    * [`AutoApply.log_applied()`](auto_apply.md#auto_apply.AutoApply.log_applied)
    * [`AutoApply.scrape_job()`](auto_apply.md#auto_apply.AutoApply.scrape_job)
    * [`AutoApply.view_jobs()`](auto_apply.md#auto_apply.AutoApply.view_jobs)
* [utils module](utils.md)
  * [`datetime_parser()`](utils.md#utils.datetime_parser)
  * [`datetime_serializer()`](utils.md#utils.datetime_serializer)



## *class* auto_apply.AutoApply(folder_name='file_templates/')

Bases: `object`

Interacts with indeed and aplication portals, 
employs semantic search to find appropriate (preset) answers used to auto-fill forms

## \_\_init_\_(folder_name='file_templates/')

## autofill_current_page(delay=0.1)

fill any form elements on the driver’s active page with preset answers

## close()

close selenium driver

## describe_element(html_el)

extracts text directly surrounding the input form element, as well as useful attributes of the element that may be descriptive of it’s purpose

> html_el
> : bs4 element to describe

> str
> : surrounding text + self.informative_input_el_attrs

## filter_jobs(jobs)

return only the jobs that fit certain criteria: haven’t been seen recently (that’s it for now)

#### Parameters

jobs
: the jobs to filter, should have the structure of the output of get_jobs()

#### Returns

list of dicts
: jobs that pass the filter

## get_best_option(options, context, form_el)

semantic search pre-set form answers based on form element and it’s context

> options
> : list of options to choose from

> context
> : string of context to inform the semantic search

> form_el
> : string of the form element itself, also to inform the semantic search

> bs4.element.Tag
> : closest matching option found

## get_description(description_page)

return the job description text from it’s webpage

#### Parameters

description_page
: a job description page

#### Returns

str
: job description text

## get_description_urls(search_page)

return urls to job description pages of every result of an indeed search result page

#### Parameters

search_page
: the indeed search results page from which to extract job description links

#### Returns

list
: urls that bring you to job description pages

## get_duplicate_element_indexes(elements)

finds duplicates in a list of bs4 elements, returns their indexes

> elements
> : bs4 elements to check for duplicates

> list[list[int]]
> : lists of duplicate’s indexes, each list contains indexes of identical elements

## get_form_answers(contexts, form_els)

semantic search pre-set form answers based on form element and it’s context

> contexts
> : list of string of context to inform the semantic search

> form_els
> : list of string of the form element itself, also to inform the semantic search

> str
> : best of the pre-set form answers to fill the form element with

## get_form_elements_html(form_page)

return list of all form elements in bs4 page

> form_page
> : the bs4 page with form elements

> list of bs4.element.Tag
> : all the bs4 form elements present in the input page

## get_indeed_apply_url(description_page)

return indeed’s url to apply to the job on the given job description page

#### Parameters

description_page
: a job description page

#### Returns

str
: application url

## get_jobs(search_urls=None, delay=1)

get the job description text and application portal url from the first page of search results 
of a list of indeed searches

#### Parameters

search_urls
: list of indeed search urls. If None, uses self.search_urls which is loaded from self.search_url_filename

#### Returns

list of dicts
: each dict corresponds to one job with:
  - apply_url: str
  <br/>
  > link to company’s application portal
  - description: str
    : job escription
  - date_scraped: datetime.datetime
    : date of the dict’s creation
  - search_url: str
    : the urls of the search results page in which this job was found

## get_page(url)

return BeautifulSoup of the page’s html, obtained through selenium

#### Parameters

url
: url of the page to get

#### Returns

BeautifulSoup
: BeautifulSoup of the page’s html

## get_query_from_html(html_el)

return all the attributes of an element in the format required for document.querySelector().

> html_el
> : the bs4 element we want to find an equivalent js query for

> str
> : query string for document.querySelector()

## get_surrounding_text(html_el, thresh=<class 'float'>)

return text of the furthest grandparent with text no greater than self.max+context_size characters

> html_el
> : bs4 element to get the surrounding text of

> str
> : text of the furthest grandparent with text no greater than self.max+context_size characters

## get_xpath_from_html(html_el, use_text=False)

return all the attributes of an element in xpath format required for selenium driver.find_elements()

> html_el
> : the bs4 element we want to find an equivalent xpath for

> use_text
> : wether or not to include the inner text of the element in the xpath

> str
> : xpath for driver.find_elements(By.XPATH, xpath)

## load_answers()

reload form answers

## load_jobs()

Load previously scraped jobs

#### Returns

list of dicts
: each dict corresponds to one job with:
  - apply_url: str
  <br/>
  > link to company’s application portal
  - description: str
    : job escription
  - date_scraped: datetime.datetime
    : date of the dict’s creation
  - search_url: str
    : the urls of the search results page in which this job was found

## log_applied(jobs)

Save jobs to self.folder_name+self.applied_jobs_filename

> jobs
> : jobs to save as applied

> None

## scrape_job(url, delay=1)

Save job page info to self.folder_name+self.scraped_jobs_filename

> url
> : url of the page to scrape

> delay
> : time in seconds to wait before repeat call

> job: dict

## view_jobs(jobs)

display job pages, record which jobs were viewed

#### Parameters

jobs
: the jobs to view, should have the structure of the output of get_jobs()

#### Returns

list of dicts
: jobs that have been viewed, with the date viewed

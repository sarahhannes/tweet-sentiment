# -*- coding: utf-8 -*-

"""Text pre-processing functions.

Usage
-----
This module is used by pipeline/clean.py and pipeline/retrain.py

Using remove_link_lemma()
--------------
How to import this:
    from text_preprocessing import remove_link_lemma
    
When you do that, you will get 1 new callable to be used when initializing vectorizer:
    remove_link_lemma

(1) Indirect usage:
    The repo's pre-built sentiment analysis model will indirectly calls remove_link_lemma during model.predict()
    
    The pre-built model can be accessed by:
        MODEL_FILEID = '1ydeM6Tiamck5sF8oMDThZIRb0xQu7Nqd'
        MODEL_URL = 'https://drive.google.com/uc?id=' + MODEL_FILEID
        MODEL_OUTPUT = 'model.pickle'
        # Download model from google drive
        gdown.download(MODEL_URL, MODEL_OUTPUT, quiet=False)
        # Load model to session
        infile = open(MODEL_OUTPUT, 'rb')
        model = pickle.load(infile)
        infile.close()

(2) Direct usage:
    When initializing new vectorizer instance by:
        tfidf = TfidfVectorizer(lowercase=False,ngram_range=(2,2), preprocessor = remove_link_lemma)
        
        or in a pipeline
        
        pipe = Pipeline([
                   ('tfidf', TfidfVectorizer(lowercase=False,
                                             ngram_range=(2,2),
                                             preprocessor = remove_link_lemma)), # vectorizer
                   ('nb', BernoulliNB()) # build model
                   ])
"""

import re
from nltk.stem import WordNetLemmatizer
import nltk

nltk.download('wordnet')
wnl = WordNetLemmatizer()


def lemmatizing(text):
    """
    input: string
    Lemmatize input using nltk WordNetLemmatizer (eg wolves -> wolf)
    output: string
    """
    return ' '.join([wnl.lemmatize(word) for word in text.split(' ')])

def remove_link(text):
    """
    input: string
    Remove links from input.
    output: string
    """
    pattern = re.compile('htt.*', re.IGNORECASE)
    return ' '.join([word for word in text.split(' ') if pattern.search(word)==None])
  
def remove_link_lemma(text):
    return remove_link(lemmatizing(text))
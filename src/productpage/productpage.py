#!/usr/bin/python
#
# Copyright 2017 Istio Authors
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.


from __future__ import print_function

import asyncio
import logging
import os
import requests
import simplejson as json
import sys
from flask import Flask, request, session, render_template, redirect
from json2html import *

# These two lines enable debugging at httplib level (requests->urllib3->http.client)
# You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
# The only thing missing will be the response.body which is not logged.
try:
    import http.client as http_client
except ImportError:
    # Python 2
    import httplib as http_client

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(process)d: %(message)s')
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.ERROR)
requests_log.propagate = True
werkzeug_log = logging.getLogger('werkzeug')
werkzeug_log.setLevel(logging.ERROR)
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

# Set the secret key to some random bytes. Keep this really secret!
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

from flask_bootstrap import Bootstrap
Bootstrap(app)

servicesDomain = "" if (os.environ.get("SERVICES_DOMAIN") == None) else "." + os.environ.get("SERVICES_DOMAIN")
detailsHostname = "details" if (os.environ.get("DETAILS_HOSTNAME") == None) else os.environ.get("DETAILS_HOSTNAME")
ratingsHostname = "ratings" if (os.environ.get("RATINGS_HOSTNAME") == None) else os.environ.get("RATINGS_HOSTNAME")
reviewsHostname = "reviews" if (os.environ.get("REVIEWS_HOSTNAME") == None) else os.environ.get("REVIEWS_HOSTNAME")

flood_factor = 0 if (os.environ.get("FLOOD_FACTOR") == None) else int(os.environ.get("FLOOD_FACTOR"))

details = {
    "name" : "http://{0}{1}:9080".format(detailsHostname, servicesDomain),
    "endpoint" : "details",
    "children" : []
}

ratings = {
    "name" : "http://{0}{1}:9080".format(ratingsHostname, servicesDomain),
    "endpoint" : "ratings",
    "children" : []
}

reviews = {
    "name" : "http://{0}{1}:9080".format(reviewsHostname, servicesDomain),
    "endpoint" : "reviews",
    "children" : [ratings]
}

productpage = {
    "name" : "http://{0}{1}:9080".format(detailsHostname, servicesDomain),
    "endpoint" : "details",
    "children" : [details, reviews]
}

service_dict = {
    "productpage" : productpage,
    "details" : details,
    "reviews" : reviews,
}

def getForwardHeaders(request):
    headers = {
        'x-request-id': request.headers.get('x-request-id'),
        'x-b3-traceid': request.headers.get('x-b3-traceid'),
        'x-b3-spanid': request.headers.get('x-b3-spanid'),
        'x-b3-sampled': request.headers.get('x-b3-sampled')
    }
    return headers


# The UI:
@app.route('/')
@app.route('/index.html')
def index():
    """ Display productpage with normal user and test user buttons"""
    global productpage

    table = json2html.convert(json=json.dumps(productpage),
                              table_attributes="class=\"table table-condensed table-bordered table-hover\"")

    return render_template('index.html', serviceTable=table)


@app.route('/health')
def health():
    return 'Product page is healthy'


@app.route('/login', methods=['POST'])
def login():
    user = request.values.get('username')
    response = app.make_response(redirect(request.referrer))
    session['user'] = user
    return response


@app.route('/logout', methods=['GET'])
def logout():
    response = app.make_response(redirect(request.referrer))
    session.pop('user', None)
    return response

# a helper function for asyncio.gather, does not return a value
async def getProductReviewsIgnoreResponse(product_id, headers):
    getProductReviews(product_id, headers)

# flood reviews with unnecessary requests to demonstrate Istio rate limiting, asynchoronously
async def floodReviewsAsynchronously(product_id, headers):
    # the response is disregarded
    await asyncio.gather(*(getProductReviewsIgnoreResponse(product_id, headers) for _ in range(flood_factor)))

# flood reviews with unnecessary requests to demonstrate Istio rate limiting
def floodReviews(product_id, headers):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(floodReviewsAsynchronously(product_id, headers))
    loop.close()

@app.route('/productpage')
def front():
    product_id = 0 # TODO: replace default value
    headers = getForwardHeaders(request)
    user = session.get('user', '')
    product = getProduct(product_id, headers)
    detailsStatus, details = getProductDetails(product_id, headers)

    if flood_factor > 0:
        floodReviews(product_id, headers)

    reviewsStatus, reviews = getProductReviews(product_id, headers)
    return render_template(
        'productpage.html',
        detailsStatus=detailsStatus,
        reviewsStatus=reviewsStatus,
        product=product,
        details=details,
        reviews=reviews,
        user=user)


# The API:
@app.route('/api/v1/products')
def productsRoute():
    headers = getForwardHeaders(request)
    return json.dumps(getProducts(headers)), 200, {'Content-Type': 'application/json'}


@app.route('/api/v1/products/<product_id>')
def productRoute(product_id):
    headers = getForwardHeaders(request)
    status, details = getProductDetails(product_id, headers)
    return json.dumps(details), status, {'Content-Type': 'application/json'}


@app.route('/api/v1/products/<product_id>/reviews')
def reviewsRoute(product_id):
    headers = getForwardHeaders(request)
    status, reviews = getProductReviews(product_id, headers)
    return json.dumps(reviews), status, {'Content-Type': 'application/json'}


@app.route('/api/v1/products/<product_id>/ratings')
def ratingsRoute(product_id):
    headers = getForwardHeaders(request)
    status, ratings = getProductRatings(product_id, headers)
    return json.dumps(ratings), status, {'Content-Type': 'application/json'}



# Data providers:
def getProducts(headers):
    trace_id = headers['x-b3-traceid']
    span_id = headers['x-b3-spanid']
    logging.info('[productpage,{0},{1}] Getting all products list'.format(trace_id, span_id))
    return [
        {
            'id': 0,
            'title': 'The Comedy of Errors',
            'descriptionHtml': '<a href="https://en.wikipedia.org/wiki/The_Comedy_of_Errors">Wikipedia Summary</a>: The Comedy of Errors is one of <b>William Shakespeare\'s</b> early plays. It is his shortest and one of his most farcical comedies, with a major part of the humour coming from slapstick and mistaken identity, in addition to puns and word play.'
        }
    ]


def getProduct(product_id, headers):
    products = getProducts(headers)
    if product_id + 1 > len(products):
        return None
    else:
        return products[product_id]


def getProductDetails(product_id, headers):
    trace_id = headers['x-b3-traceid']
    span_id = headers['x-b3-spanid']
    logging.info('[productpage,{0},{1}] Asking for details of product {2}'.format(trace_id, span_id, product_id))
    try:
        url = details['name'] + "/" + details['endpoint'] + "/" + str(product_id)
        res = requests.get(url, headers=headers, timeout=3.0)
    except:
        res = None
    if res and res.status_code == 200:
        return 200, res.json()
    else:
        status = res.status_code if res is not None and res.status_code else 500
        return status, {'error': 'Sorry, product details are currently unavailable for this book.'}


def getProductReviews(product_id, headers):
    trace_id = headers['x-b3-traceid']
    span_id = headers['x-b3-spanid']
    logging.info('[productpage,{0},{1}] Asking for reviews of product {2}'.format(trace_id, span_id, product_id))
    ## Do not remove. Bug introduced explicitly for illustration in fault injection task
    ## TODO: Figure out how to achieve the same effect using Envoy retries/timeouts
    for _ in range(2):
        try:
            url = reviews['name'] + "/" + reviews['endpoint'] + "/" + str(product_id)
            res = requests.get(url, headers=headers, timeout=3.0)
        except:
            res = None
        if res and res.status_code == 200:
            return 200, res.json()
    status = res.status_code if res is not None and res.status_code else 500
    return status, {'error': 'Sorry, product reviews are currently unavailable for this book.'}


def getProductRatings(product_id, headers):
    trace_id = headers['x-b3-traceid']
    span_id = headers['x-b3-spanid']
    logging.info('[productpage,{0},{1}] Asking for ratings of product {2}'.format(trace_id, span_id, product_id))
    try:
        url = ratings['name'] + "/" + ratings['endpoint'] + "/" + str(product_id)
        res = requests.get(url, headers=headers, timeout=3.0)
    except:
        res = None
    if res and res.status_code == 200:
        return 200, res.json()
    else:
        status = res.status_code if res is not None and res.status_code else 500
        return status, {'error': 'Sorry, product ratings are currently unavailable for this book.'}

class Writer(object):
    def __init__(self, filename):
        self.file = open(filename,'w')

    def write(self, data):
        self.file.write(data)

    def flush(self):
        self.file.flush()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: %s port" % (sys.argv[0]))
        sys.exit(-1)

    p = int(sys.argv[1])
    sys.stderr = Writer('stderr.log')
    sys.stdout = Writer('stdout.log')
    print("start at port %s" % (p))
    app.run(host='0.0.0.0', port=p, debug=False, threaded=True)

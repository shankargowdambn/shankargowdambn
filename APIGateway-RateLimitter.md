# Rate Limiter

References: [ByteByteGo](https://bytebytego.com/courses/system-design-interview/design-a-rate-limiter)

In a network system, a rate limiter is used to control the rate of traffic sent by a client or a service. In the HTTP world, a rate limiter limits the number of client requests allowed to be sent over a specified period. If the API request count exceeds the threshold defined by the rate limiter, all the excess calls are blocked

***HTTP 429 : response status code indicates a user has sent too many requests***

Almost all APIs published by large tech companies enforce some form of rate limiting.

Cloud microservices [4] have become widely popular and rate limiting is usually implemented within a component called API gateway. API gateway is a fully managed service that supports rate limiting, SSL termination, authentication, IP whitelisting, servicing static content, etc. For now, we only need to know that the API gateway is a middleware that supports rate limiting.

For example,
Twitter limits the number of tweets to 300 per 3 hours [2].
Google docs APIs have the following default limit: 300 per user per 60 seconds for read requests [3].

A rate limiter prevents DoS attacks, either intentional or unintentional, by blocking the excess calls.

## Algorithms for rate limiting

1. Token bucket
    - Both Amazon [5] and Stripe [6] use this algorithm to throttle their API requests.
2. Leaking bucket
    - Shopify, an ecommerce company, uses leaky buckets for rate-limiting
3. Fixed window counter
4. Sliding window log
5. Sliding window counter

## Reference materials

[1] Rate-limiting strategies and techniques:
<https://cloud.google.com/solutions/rate-limiting-strategies-techniques>

[2] Twitter rate limits: <https://developer.twitter.com/en/docs/basics/rate-limits>

[3] Google docs usage limits: <https://developers.google.com/docs/api/limits>

[4] IBM microservices: <https://www.ibm.com/cloud/learn/microservices>

[5] Throttle API requests for better throughput:
<https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html>

[6] Stripe rate limiters: <https://stripe.com/blog/rate-limiters>

[7] Shopify REST Admin API rate limits:
<https://help.shopify.com/en/api/reference/rest-admin-api-rate-limits>

[8] Better Rate Limiting With Redis Sorted Sets:
<https://engineering.classdojo.com/blog/2015/02/06/rolling-rate-limiter/>

[9] System Design — Rate limiter and Data modelling:
<https://medium.com/@saisandeepmopuri/system-design-rate-limiter-and-data-modelling-9304b0d18250>

[10] How we built rate limiting capable of scaling to millions of domains:
<https://blog.cloudflare.com/counting-things-a-lot-of-different-things/>

[11] Redis website: <https://redis.io/>

[12] Lyft rate limiting: <https://github.com/lyft/ratelimit>

[13] Scaling your API with rate limiters:
<https://gist.github.com/ptarjan/e38f45f2dfe601419ca3af937fff574d#request-rate-limiter>

[14] What is edge computing:
<https://www.cloudflare.com/learning/serverless/glossary/what-is-edge-computing/>

[15] Rate Limit Requests with Iptables: <https://blog.programster.org/rate-limit-requests-with-iptables>

[16] OSI model:
<https://en.wikipedia.org/wiki/OSI_model#Layer_architecture>

# console_fast_autocomplete

Fast automplete implementation based on Redis NoSQL, console version.


## General information

### Problem

Imagine situation when you need provide autocomplete for some data list. In case when you using SQL  probably you will do something like this:

```SQL
select * from table_name where table_field like 'search%'
```

Probably you know, that when you database contains significant amount of data you will get essential decreasing of data processing.

### Disclaimer

This repository contains dictionaries found on some FTPs and other repos. They can be found in `data` folder.

## Solution

#### Base information

You can use Redis NoSQL to perform fast autocomplete. First of all you need load all data into Redis database and then give interface to perform sarch queries.

#### Loading data

First of all we will use [`ZADD`](https://redis.io/commands/zadd) command to load items into sorted set. We will specify same score `0.0` to each item, so them will sorted lexicographically in the set.


To implement **case insensitive search** we will use some little trick. Before adding each item to the set we will convert it to lowercase and will add original item after `:` separator. So when we have want add word `Wood` to the set, actually we will add `wood:Wood`. In this case we will be able to perform case insensitive search and also save original word.

We will use pipelines (part of `redis` Python library) to increase loading speed. They will help us to buffer `ZADD` commands and reduce the number of back-and-forth TCP packets between the client and server. They helps us to dramatically increase the loading performance.

#### Performing search

We will use [`ZRANGEBYLEX`](https://redis.io/commands/zrangebylex) command and will load all strings which starts with query string. So it's will be actual implementation of autocomplete. BTW, superfast autocomplete: we can perform search for string `alexa` for **`520679`** items just in **30-35ms** at my laptop.


## Installation

Just clone this repository using git and then and install dependancies using:

`pip install -r requirements.txt`

## Usage

### Configuration file

You can find example configuration file in:

`.\conf\default.conf`

You need specify connection to `redis`, folder with data and temporary

```ini
[main]
temp_path=./tmp

[redis]
host=localhost
port=6379
password=
db=0

[data]
main_source=./data/
```

Where:

* `redis` connection to redis;
* `data::main_source` - folder with data;
* `main::temp_path` - folder for `.zip` files unpacking


### Initializing database

You can load all information from data files using:

`string_search.py --config ./conf/default.conf --init-data`

program will look for all files in this folder. If `.zip` file will be found, it will be uncompressed into temporary folder for further loading.

This operation can took long time, up to 1 minute on slow machines.

### Performing search

To perform search for `alexa` query you should use:

`string_search.py --config ./conf/default.conf --search alexa`

### Checking items count

You can check count of items in database by using:

`string_search.py --config ./conf/default.conf --get-length`

Enjoy!
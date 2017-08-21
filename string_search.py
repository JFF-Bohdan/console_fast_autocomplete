import argparse
import codecs
import configparser
import errno
import functools
import os
import time
import zipfile

import redis


REDIS_ZSET_NAME = "string_search_zset"
TMP_DIR = "./tmp"


def main():
    tm_begin = time.time()
    args, config = parse_command_line()

    redis_connection = redis.Redis(
        host=config.get("redis", "host"),
        port=config.getint("redis", "port"),
        password=config.get("redis", "password"),
        db=config.getint("redis", "db")
    )

    if args.drop_data:
        drop_data(redis_connection, REDIS_ZSET_NAME)

    if args.init_data:
        data_dir = config.get("data", "main_source")
        tmp_dir = config.get("main", "temp_path")

        init_data(redis_connection, REDIS_ZSET_NAME, data_dir, tmp_dir)

    if args.search:
        query_data(redis_connection, REDIS_ZSET_NAME, args.search)

    if args.get_length:
        get_data_length(redis_connection, REDIS_ZSET_NAME)

    elapsed = round(time.time() - tm_begin, 3)
    print("done @ {}s".format(elapsed))


def parse_command_line():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config",
        metavar="FILE",
        help="use FILE as configuration file"
    )

    parser.add_argument(
        "--init-data",
        action="store_true",
        help="initialize names list in database"
    )

    parser.add_argument(
        "--get-length",
        action="store_true",
        help="get length of data in memory"
    )

    parser.add_argument(
        "--drop-data",
        action="store_true",
        help="remove names from database"
    )

    parser.add_argument(
        "--search",
        action="store",
        help="search for value"
    )

    args = parser.parse_args()

    config = configparser.RawConfigParser()
    config.read(args.config)

    return args, config


def drop_data(redis_connection, set_name):
    redis_connection.delete(set_name)


def init_data(redis_connection, set_name, data_folder, temp_folder):
    if not make_temp_folder(temp_folder):
        exit(1)

    print("loading data into redis-database")
    drop_data(redis_connection, set_name)

    files = get_data_files(data_folder)
    print("files = {}".format(files))
    if files is None:
        exit(2)

    total_lines_loaded = 0
    total_items_added = 0
    for file_name in files:
        print("\tloading data from: {}".format(os.path.basename(file_name)))

        lines_loaded, items_added = upload_data_from_file(redis_connection, set_name, file_name, temp_folder)

        print("\t\tlines loaded = {}".format(lines_loaded))
        print("\t\tlines_added  = {}".format(items_added))

        total_lines_loaded += lines_loaded
        total_items_added += items_added

    print("total_lines_loaded = {}".format(total_lines_loaded))
    print("total_items_added  = {}".format(total_items_added))


def upload_data_from_file(redis_connection, set_name, file_name, temp_folder):
    extension = os.path.splitext(file_name)[1]

    need_remove_at_exit = False
    if str(extension).lower() == ".zip":
        file_name = unzip_file(file_name, temp_folder)
        need_remove_at_exit = True

    lines_loaded = 0
    pipe = redis_connection.pipeline()
    with codecs.open(file_name, "r", "utf-8") as file:
        for line in file:
            line = str(line).strip()
            if (line.startswith("#")) or (len(line) == 0):
                continue

            pipe.zadd(set_name, "{}:{}".format(line.lower(), line), 0)
            lines_loaded += 1

        items_added = functools.reduce(lambda x, y: x + y, pipe.execute(), 0)

    if need_remove_at_exit:
        os.remove(file_name)

    return lines_loaded, items_added


def unzip_file(file_name, temp_folder):
    with zipfile.ZipFile(file_name, "r") as archive:
        compressed_filename = archive.filelist[0].filename

        archive.extract(compressed_filename, temp_folder)
        res = os.path.join(temp_folder, compressed_filename)

        return os.path.normpath(os.path.abspath(res))


def get_data_files(path):
    abs_data_folder = os.path.normpath(os.path.abspath(path))

    if not os.path.exists(abs_data_folder):
        print("ERR: path '{}' does not exists".format(path))
        return None

    if not os.path.isdir(abs_data_folder):
        print("ERR: '{}' is not a directory".format(path))
        return None

    res = []
    for file_name in os.listdir(abs_data_folder):
        abs_file_name = os.path.join(abs_data_folder, file_name)
        abs_file_name = os.path.normpath(os.path.abspath(abs_file_name))
        if not os.path.isfile(abs_file_name):
            continue

        res.append(abs_file_name)

    return res


def make_temp_folder(path):
    abs_temp_folder = os.path.normpath(os.path.abspath(path))
    if not os.path.exists(abs_temp_folder):
        ok, error_message = mkdir_p_ex(abs_temp_folder)
        if not ok:
            print("Error! can't make directory '{}': {}".format(path, error_message))
            return False

    if not os.path.isdir(abs_temp_folder):
        print("ERR: '{}' is not a directory".format(path))
        return False

    return True


def mkdir_p_ex(path):
    try:
        if os.path.exists(path) and os.path.isdir(path):
            return True, None

        os.makedirs(path)
        return True, None
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            return True, None
        else:
            return False, str(exc)
    except Exception as e:
        return False, str(e)


def query_data(redis_connection, set_name, query):
    query = str(query).strip().lower()
    print("query for '{}'".format(query))

    data = redis_connection.zrangebylex(set_name, "[{}".format(query), "[{}\xff".format(query))
    print("found {} items".format(len(data)))

    for index, item in enumerate(data):
        item = item.decode("utf-8")
        item = item[str(item).index(":") + 1 : ]
        print("\t[{}]: {}".format(index + 1, item))


def get_data_length(redis_connection, set_name):
    data_length = 0
    if redis_connection.exists(set_name):
        data_length = redis_connection.zcard(set_name)

    print("data_length = {}".format(data_length))


if __name__ == "__main__":
    main()

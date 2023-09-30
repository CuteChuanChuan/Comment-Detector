"""
This module contains utility functions for mongodb to analyze data and make graphs.
"""
import pytz
import pandas as pd
from uuid import uuid4
from itertools import combinations
from typing import Tuple, Any
from datetime import datetime, timedelta
from .config_dashboard import db


BATCH_SIZE = 10000
NUM_ARTICLES = 100

current_timezone = pytz.timezone("Asia/Taipei")
current_time = datetime.now(current_timezone).replace(
    hour=0, minute=0, second=0, microsecond=0
)


# Section: overall information about crawling data
def count_articles(target_collection: str) -> int:
    """
    count number of articles in mongodb
    :param target_collection: target collection
    :return: number of articles
    """
    return db[target_collection].count_documents({})


def count_comments(target_collection: str) -> int:
    """
    count number of articles in mongodb
    :param target_collection: target collection
    :return: number of articles
    """
    num_comments = 0
    cursor = db[target_collection].find({}, {"article_data.num_of_comment": 1})
    cursor.batch_size(BATCH_SIZE)
    for document in cursor:
        article_data = document.get("article_data", {})
        comments = article_data.get("num_of_comment", 0)
        num_comments += comments
    return num_comments


def count_accounts(target_collection: str) -> int:
    """
    count number of unique accounts in mongodb
    :param target_collection: target collection
    :return: number of articles
    """
    unique_accounts = set()
    cursor = db[target_collection].find({}, {"article_data.author": 1})
    cursor.batch_size(BATCH_SIZE)
    for document in cursor:
        article_data = document.get("article_data", {})
        unique_accounts.add(article_data["author"])
    pipeline = [
        {"$unwind": "$article_data.comments"},
        {
            "$group": {
                "_id": None,
                "unique_commenter_ids": {
                    "$addToSet": "$article_data.comments.commenter_id"
                },
            }
        },
    ]
    result = list(db[target_collection].aggregate(pipeline))
    unique_commenter_ids = result[0]["unique_commenter_ids"] if result else []
    for commenter in unique_commenter_ids:
        unique_accounts.add(commenter)
    return len(unique_accounts)


# Section: operations about article
def get_top_n_breaking_news(target_collection: str, num_articles: int) -> list:
    """
    return top n breaking news defined by title including <爆卦>
    :param target_collection: target collection
    :param num_articles: number of articles
    """
    breaking_news = list(
        db[target_collection]
        .find(
            {"article_data.title": {"$regex": "爆卦", "$options": "i"}},
            {
                "article_data.title": 1,
                "article_data.author": 1,
                "article_data.num_of_comment": 1,
                "article_url": 1,
                "_id": 0,
            },
        )
        .sort("article_data.num_of_comment", -1)
        .limit(num_articles)
    )
    return breaking_news


def get_top_n_favored_articles(target_collection: str, num_articles: int) -> list:
    """
    return top n favored articles defined by <num of favor> subtracting <num of against> >= 100
    :param target_collection: target collection
    :param num_articles: number of articles
    """
    pipelines = [
        {
            "$project": {
                "_id": 0,
                "article_url": 1,
                "article_data.title": 1,
                "article_data.author": 1,
                "article_data.num_of_comment": 1,
                "favor_difference": {
                    "$subtract": [
                        "$article_data.num_of_favor",
                        "$article_data.num_of_against",
                    ]
                },
            }
        },
        {"$match": {"favor_difference": {"$gte": 100}}},
        {"$sort": {"favor_difference": -1}},
        {"$limit": num_articles},
    ]
    return list(db[target_collection].aggregate(pipelines))


def get_past_n_days_article_title(target_collection: str, n_days: int) -> list[dict]:
    """
    return article titles of the past n days
    :param target_collection: target collection
    :param n_days: number of days
    """
    n_days_ago_timestamp = int((current_time - timedelta(days=n_days)).timestamp())
    current_timestamp = int(current_time.timestamp())
    pipeline = [
        {
            "$match": {
                "article_data.time": {
                    "$gte": n_days_ago_timestamp,
                    "$lte": current_timestamp,
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "article_url": 1,
                "article_text": "$article_data.title",
            }
        },
    ]

    cursor = db[target_collection].aggregate(pipeline).batch_size(BATCH_SIZE)
    return list(cursor)


def get_past_n_days_comments(target_collection: str, n_days: int) -> list[dict]:
    """
    return the n days of comments
    :param target_collection: target collection
    :param n_days: number of days
    """
    n_days_ago_timestamp = int((current_time - timedelta(days=n_days)).timestamp())
    current_timestamp = int(current_time.timestamp())
    pipeline = [
        {
            "$match": {
                "article_data.time": {
                    "$gte": n_days_ago_timestamp,
                    "$lte": current_timestamp,
                }
            }
        },
        {"$project": {"_id": 0, "article_url": 1, "article_data.comments": 1}},
        {"$unwind": "$article_data.comments"},
        {
            "$project": {
                "_id": 0,
                "article_url": 1,
                "article_text": "$article_data.comments.comment_content",
            }
        },
    ]
    cursor = db[target_collection].aggregate(pipeline).batch_size(BATCH_SIZE)
    return list(cursor)


# Section: operations about accounts
def extract_all_articles_commenter_involved(
    target_collection: str, account: str
) -> list[dict]:
    """
    return all articles which have been commented by commenter in users' query
    :param target_collection: target collection
    :param account: account name of the commenter
    """
    cursor = (
        db[target_collection]
        .find(
            {"article_data.comments.commenter_id": account},
            {"_id": 0, "article_url": 1, "article_data.title": 1},
        )
        .batch_size(BATCH_SIZE)
    )
    articles_collection = []
    for article in cursor:
        articles_collection.append(
            {
                "article_url": article["article_url"],
                "article_title": article["article_data"]["title"],
            }
        )
    return articles_collection


# Section: operations to generate network graph
def extract_author_info_from_articles_title_having_keywords(
    target_collection: str, keyword: str, num_articles: int
) -> list[dict]:
    """
    return author_id and ipaddress of articles having keywords
    :param target_collection: target collection
    :param keyword: keyword
    :param num_articles: number of articles
    """

    cursor = (
        db[target_collection]
        .find(
            {"article_data.title": {"$regex": keyword, "$options": "i"}},
            {
                "_id": 0,
                "article_url": 1,
                "article_data.author": 1,
                "article_data.ipaddress": 1,
                "article_data.time": 1,
                "article_data.num_of_comment": 1,
            },
        )
        .sort("article_data.num_of_comment", -1)
        .limit(num_articles)
    )
    return list(cursor)


def extract_commenter_info_from_article_with_article_url(
    target_collection: str, article_data: dict
) -> list[dict]:
    """
    return commenter_id and ipaddress of article with article_url
    :param target_collection: target collection
    :param article_data: article data
    """
    article_published_time = article_data["article_data"]["time"]
    article_url = article_data["article_url"]
    pipeline = [
        {"$match": {"article_url": article_url}},
        {"$unwind": "$article_data.comments"},
        {
            "$addFields": {
                "time_difference": {
                    "$subtract": [
                        "$article_data.comments.comment_time",
                        article_published_time,
                    ]
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "article_data.article_url": 1,
                "article_data.comments": 1,
                "time_difference": 1,
            }
        },
    ]
    cursor = db[target_collection].aggregate(pipeline)
    return list(cursor)


def summarize_commenters_metadata(commenters_data: list, temp_dict: dict) -> dict:
    """
    summarize commenters metadata for network graph
    :param commenters_data: commenters data
    :param temp_dict: temp dict storing commenters info
    """
    for commenter in commenters_data:
        temp_dict[commenter.get("article_data").get("comments").get("commenter_id")][
            "freq"
        ] += 1

        comment_type = commenter.get("article_data").get("comments").get("comment_type")
        if comment_type == "推":
            temp_dict[
                commenter.get("article_data").get("comments").get("commenter_id")
            ]["agree"] += 1
        elif comment_type == "噓":
            temp_dict[
                commenter.get("article_data").get("comments").get("commenter_id")
            ]["disagree"] += 1
        else:
            temp_dict[
                commenter.get("article_data").get("comments").get("commenter_id")
            ]["reply"] += 1

        temp_dict[commenter.get("article_data").get("comments").get("commenter_id")][
            "time_total"
        ] += commenter.get("time_difference")

        temp_dict[commenter.get("article_data").get("comments").get("commenter_id")][
            "time_avg"
        ] = (
            temp_dict[
                commenter.get("article_data").get("comments").get("commenter_id")
            ]["time_total"]
            / temp_dict[
                commenter.get("article_data").get("comments").get("commenter_id")
            ]["freq"]
        )
    return temp_dict


def convert_commenters_metadata_to_dataframe(commenter_metadata: dict) -> pd.DataFrame:
    """
    convert commenters metadata to dataframe
    :param commenter_metadata: temp dict storing commenters info
    """
    data = []
    for commenter_id, stats in commenter_metadata.items():
        temp = stats.copy()
        temp["commenter_id"] = commenter_id
        data.append(temp)
    return pd.DataFrame(data)


def extract_top_freq_commenter_id(meta_df: pd.DataFrame, num_commenters: int) -> list:
    return (
        meta_df.sort_values("freq", ascending=False)
        .head(num_commenters)["commenter_id"]
        .to_list()
    )


def extract_top_agree_commenter_id(meta_df: pd.DataFrame, num_commenters: int) -> list:
    return (
        meta_df.sort_values("agree", ascending=False)
        .head(num_commenters)["commenter_id"]
        .to_list()
    )


def extract_top_disagree_commenter_id(
    meta_df: pd.DataFrame, num_commenters: int
) -> list:
    return (
        meta_df.sort_values("disagree", ascending=False)
        .head(num_commenters)["commenter_id"]
        .to_list()
    )


def extract_top_short_comment_latency_commenter_id(
    meta_df: pd.DataFrame, num_commenters: int
) -> list:
    return (
        meta_df.sort_values("time_avg", ascending=True)
        .head(num_commenters)["commenter_id"]
        .to_list()
    )


def check_commenter_in_article_filter_by_article_url(
    target_collection: str, commenter_id: str, article_url: str
) -> bool:
    query = {
        "article_url": article_url,
        "article_data.comments": {"$elemMatch": {"commenter_id": commenter_id}},
    }
    return db[target_collection].find_one(query) is not None


# Section: functions needed for network graph
# Rationale: (1) filter articles by keyword and sort by number of comments
# Rationale: (2) get top n commenters with 2 types of comments
# Rationale: (3) get all combinations of the top n commenters
# Rationale: (4) compute the concurrency of each combination -> divide by number of articles
# Rationale: (5) compute each commenter's response latency -> draw graph
def query_articles_store_temp_collection(
    keyword: str, target_collection: str
) -> Tuple[str, str, str]:
    if target_collection not in ["gossip", "politics"]:
        raise ValueError("Invalid target collection (only gossip, politics)")
    collection_name = f"concurrency_collection_{keyword}_{uuid4()}"
    pipeline = [
        {"$match": {"article_data.title": {"$regex": keyword, "$options": "i"}}},
        {"$sort": {"article_data.num_of_comment": -1}},
        {"$limit": NUM_ARTICLES},
        {"$out": collection_name},
    ]

    db[target_collection].aggregate(pipeline)
    return collection_name, target_collection, keyword


def list_top_n_commenters_filtered_by_comment_type(
    temp_collection: str, comment_type: str, num_commenters: int = 20
) -> tuple[list[Any], int]:
    """
    list top n commenters and number of comments filtered by comment type
    :param temp_collection: temporary collection
    :param comment_type: comment type  (either '推' or '噓')
    :param num_commenters: how many commenters to return
    :return: list of top n commenters and number of comments filtered by comment type
    """
    if comment_type not in ["推", "噓"]:
        raise ValueError("Invalid comment type (only accept '推' or '噓')")

    pipeline = [
        {"$unwind": "$article_data.comments"},
        {"$match": {"article_data.comments.comment_type": comment_type}},
        {
            "$group": {
                "_id": "$article_data.comments.commenter_id",
                "article_ids": {"$addToSet": "$_id"},
            }
        },
        {"$project": {"count": {"$size": "$article_ids"}}},
        {"$sort": {"count": -1}},
        {"$limit": num_commenters},
    ]

    results = db[temp_collection].aggregate(pipeline)
    return list(results), num_commenters


def generate_all_combinations(commenters: list[dict]) -> list[tuple]:
    """
    generate all combinations of commenters
    :param commenters: list of commenters with element format "{'_id': 'coffee112', 'count': 119}"
    """
    commenters = [commenter["_id"] for commenter in commenters]
    return list(combinations(commenters, 2))


def compute_concurrency(ids: tuple, temp_collection: str, comment_type: str):
    if comment_type not in ["推", "噓"]:
        raise ValueError("Invalid comment type (only accept '推' or '噓')")
    pipeline = [
        {
            "$match": {
                "$and": [
                    {
                        "article_data.comments": {
                            "$elemMatch": {
                                "commenter_id": ids[0],
                                "comment_type": comment_type,
                            }
                        }
                    },
                    {
                        "article_data.comments": {
                            "$elemMatch": {
                                "commenter_id": ids[1],
                                "comment_type": comment_type,
                            }
                        }
                    },
                ]
            }
        },
        {"$count": "count_articles"},
    ]
    result = list(db[temp_collection].aggregate(pipeline))
    concurrency = result[0]["count_articles"] / NUM_ARTICLES if len(result) != 0 else 0
    return ids[0], ids[1], concurrency


def weight_to_color(weight, weights, cmap):
    norm_weight = (weight - min(weights)) / (max(weights) - min(weights))
    rgba = cmap(norm_weight)
    return f"rgb({rgba[0]*255}, {rgba[1]*255}, {rgba[2]*255})"


if __name__ == "__main__":
    start_time = datetime.now()
    print(f"total time: {datetime.now() - start_time}")

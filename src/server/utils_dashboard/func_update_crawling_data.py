from dash import html
from .utils_mongodb import (
    retrieve_articles_count_sum,
    retrieve_comments_count_sum,
    retrieve_accounts_count_sum,
)


def update_layout():
    total_articles = retrieve_articles_count_sum()
    total_comments = retrieve_comments_count_sum()
    total_accounts = retrieve_accounts_count_sum()

    return [
        html.Div(
            [
                html.H4("文章數", style={"textAlign": "center"}),
                html.H1(f"{total_articles:,}", style={"textAlign": "center"}),
                html.H5("篇", style={"textAlign": "center"}),
            ],
            style={"width": "33%", "display": "inline-block"},
        ),
        html.Div(
            [
                html.H4("留言數", style={"textAlign": "center"}),
                html.H1(f"{total_comments:,}", style={"textAlign": "center"}),
                html.H5("則", style={"textAlign": "center"}),
            ],
            style={"width": "33%", "display": "inline-block"},
        ),
        html.Div(
            [
                html.H4("帳號數", style={"textAlign": "center"}),
                html.H1(f"{total_accounts:,}", style={"textAlign": "center"}),
                html.H5("個", style={"textAlign": "center"}),
            ],
            style={"width": "33%", "display": "inline-block"},
        ),
    ]

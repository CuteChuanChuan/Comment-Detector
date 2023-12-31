import time
import plotly.graph_objects as go
from collections import defaultdict
from .config_dashboard import timestamp_to_datetime, db


def commenter_no_result_figure():
    return {
        "layout": {
            "xaxis": {"visible": False, "range": [0, 1]},
            "yaxis": {"visible": False, "range": [0, 1]},
            "annotations": [
                {
                    "text": "查無資料",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 20},
                }
            ],
        }
    }


def heatmap_commenter_activities(account_id: str):
    pipeline = [
        {"$match": {"article_data.comments.commenter_id": account_id}},
        {"$unwind": "$article_data.comments"},
        {"$match": {"article_data.comments.commenter_id": account_id}},
        {
            "$group": {
                "_id": "$_id",
                "article_url": {"$first": "$article_url"},
                "comment_time": {"$first": "$article_data.comments.comment_time"},
            }
        },
    ]
    active_time = []
    for board in ["gossip", "politics"]:
        records = db[board].aggregate(pipeline)
        for result in records:
            if result["comment_time"] is not None:
                result["comment_time"] = timestamp_to_datetime(result["comment_time"])
                result["comment_weekday"] = result["comment_time"].strftime("%A")
                result["comment_hour"] = result["comment_time"].hour
                active_time.append(result)

    if len(active_time) > 0:
        frequency_counter = defaultdict(lambda: defaultdict(int))
        for entry in active_time:
            weekday = entry["comment_weekday"]
            hour = entry["comment_hour"]
            frequency_counter[weekday][hour] += 1

        weekdays = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        days = []
        hours = []
        counts = []

        for weekday in weekdays:
            for hour in range(24):
                counts.append(frequency_counter[weekday].get(hour, 0))
                days.append(weekday)
                hours.append(hour)

        colorscale = [[0, "white"], [1, "black"]]
        data = [
            go.Heatmap(z=counts, y=days, x=hours, xgap=5, ygap=5, colorscale=colorscale)
        ]

        layout = go.Layout(
            title="留言時段分佈",
            xaxis=dict(tickmode="linear"),
            shapes=[
                # Rectangle to highlight Monday to Friday, 08-18
                dict(
                    type="rect",
                    x0=7.5,
                    x1=18.5,
                    y0=4.5,
                    y1=-0.5,
                    line=dict(color="red", width=3),
                    fillcolor="rgba(255, 0, 0, 0.05)",
                )
            ],
        )

        fig = go.Figure(data=data, layout=layout)
        return fig
    return commenter_no_result_figure()


if __name__ == "__main__":
    start = time.time()
    heatmap_commenter_activities(account_id="coffee112").show()
    print(f"Time: {time.time() - start}")

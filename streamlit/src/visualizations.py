import plotly.express as px
import plotly.graph_objects as go

def bar(df, x, y, title, labels=None, text=None, **kwargs):
    fig = px.bar(df, x=x, y=y, title=title, labels=labels, text=text, **kwargs)
    fig.update_layout(hovermode="x unified")
    return fig

def line(df, x, y, title, color=None, labels=None, **kwargs):
    fig = px.line(df, x=x, y=y, title=title, color=color, markers=True, labels=labels, **kwargs)
    return fig

def scatter(df, x, y, title, color=None, hover_data=None, labels=None, **kwargs):
    fig = px.scatter(
        df, x=x, y=y, title=title, color=color,
        hover_data=hover_data, labels=labels, **kwargs
    )
    return fig

def heatmap(matrix, title):
    fig = px.imshow(
        matrix,
        text_auto=".3f",
        aspect="auto",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        title=title,
    )
    return fig

def horizontal_ranking(df, x, y, title, labels=None):
    fig = px.bar(
        df.sort_values(x),
        x=x, y=y, orientation="h",
        title=title, labels=labels,
        text=x,
    )
    return fig

def reference_line(fig, y=0):
    fig.add_hline(y=y, line_dash="dash")
    return fig

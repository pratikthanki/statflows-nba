import os
import pandas as pd
import numpy as np

from flask import Flask, redirect, url_for, session
from flask_oauth import OAuth
from dash_google_auth import GoogleOAuth

from urllib.parse import urljoin

import dash
from dash.dependencies import Input, Output
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go

from shared_config import sql_config
from shared_modules import load_data
from app_styles import DEFAULT_IMAGE, HEADER_STYLE, TABLE_STYLE, SELECTED_TAB_STYLE, \
    SINGLE_TAB_STYLE, ALL_TAB_STYLE, EVENT_DEFINITIONS

from nba_settings import authorized_app_emails
from teams import TEAMS
from court import court_plot
from sql_queries import team_roster_query, team_query, shot_chart_query, team_game_stats_query, \
    team_season_stats_query, SHOT_PLOT_COLUMNS, TEAM_COLUMNS, TEAM_STATS_COLUMNS, CURRENT_ROSTER_COLUMNS

server = Flask(__name__)

app = dash.Dash(
    name='nba_app',
    server=server,
    url_base_pathname='/',
    external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css'],
    suppress_callback_exceptions=True)

server.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersekrit")
server.config["GOOGLE_OAUTH_CLIENT_ID"] = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
server.config["GOOGLE_OAUTH_CLIENT_SECRET"] = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")

# one of the Redirect URIs from Google APIs console
REDIRECT_URI = '/oauth2callback'

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

auth = GoogleOAuth(
    app,
    authorized_app_emails,
)


def get_shots(player):
    if player:
        shot_query = shot_chart_query.format(player, '', '')
        shot_plot = load_data(shot_query, sql_config, 'nba', SHOT_PLOT_COLUMNS)

        return shot_plot


def player_card(player):
    rows = []
    df = rosters[rosters['PlayerId'] == str(player)]

    if len(df) > 0:
        df = df[['Height', 'Weight', 'Position', 'DoB',
                 'Age', 'Experience', 'School']].copy()
        df = pd.DataFrame({'Metric': df.columns, 'Value': df.iloc[-1].values})

    for i in range(len(df)):
        row = []
        for col in df.columns:
            value = df.iloc[i][col]
            style = {'align': 'center', 'padding': '5px', 'color': 'black',
                     'border': 'white', 'text-align': 'center', 'font-size': '14px'}
            row.append(html.Td(value, style=style))

        rows.append(html.Tr(row))

    return html.Div(children=[
        html.Table(rows, style=TABLE_STYLE),
        dcc.Link(html.Button('MORE STATS', id='player-drilldown-' + str(player), style={
            'font-size': '12px', 'color': 'darkgrey', 'font-weight': 'bold', 'border': 'none'}),
                 href='/player/' + str(player))
    ])


def current_roster(df, team_id=None):
    if team_id is not None:
        df = df[df['TeamId'] == str(team_id)]

    team_dict = {}
    cols = df['Position'].unique()

    for position in cols:
        team_dict[position] = np.array(
            df.loc[df['Position'] == position, 'PlayerId'])

    roster = pd.DataFrame(dict([(k, pd.Series(v))
                                for k, v in team_dict.items()]))
    roster = roster.fillna('')

    return roster


def current_roster_stats(df, team_id=None):
    if team_id is not None:
        return df[df['TeamId'] == str(team_id)]
    else:
        return df


def player_image(player):
    if player != '':
        img = rosters.loc[rosters['PlayerId'] == player, 'PlayerImg']
        img = img.iloc[0] if len(img) > 0 else DEFAULT_IMAGE

        name = rosters.loc[rosters['PlayerId'] == player, 'Player']
        name = name.iloc[0] if len(name) > 0 else 'Name Missing'

        return html.Div(children=[
            html.Img(src=str(img), style={
                'height': '160px'}, className='image'),
            html.Div(html.H4(str(name),
                             style={'font-size': '22px',
                                    'text-align': 'center'})),
            html.Div(player_card(player), className='overlay')],
            className='container', style={'width': '100%', 'height': '100%', 'position': 'relative'})


def build_table(df, table_setting='Summary'):
    rows = []
    if df is not None:
        for i in range(len(df)):
            row = []
            for col in df.columns:
                value = player_image(df.iloc[i][col]) if table_setting == 'Summary' else df.iloc[i][col]
                style = {'align': 'center', 'padding': '3px', 'text-align': 'center',
                         'font-size': '12px'}
                row.append(html.Td(value, style=style))

                if i % 2 == 0 and 'background-color' not in style:
                    style['background-color'] = '#f2f2f2'

            rows.append(html.Tr(row))

        return html.Table(
            [html.Tr([html.Th(col, style=HEADER_STYLE) for col in df.columns])] + rows, style=TABLE_STYLE)


def shot_map(data):
    if data is not None:
        made_x = data[data['EType'] == 1]['LocationX']
        made_y = data[data['EType'] == 1]['LocationY']

        missed_x = data[data['EType'] == 2]['LocationX']
        missed_y = data[data['EType'] == 2]['LocationY']

        return html.Div(
            dcc.Graph(
                id='shot-plot',
                figure={
                    'data': [
                        go.Scatter(
                            x=made_x,
                            y=made_y,
                            mode='markers',
                            name='Made Shot',
                            opacity=0.7,
                            marker=dict(
                                size=5,
                                color='rgba(0, 200, 100, .8)',
                                line=dict(
                                    width=1,
                                    color='rgb(0, 0, 0, 1)'
                                )
                            )
                        ),
                        go.Scatter(
                            x=missed_x,
                            y=missed_y,
                            mode='markers',
                            name='Missed Shot',
                            opacity=0.7,
                            marker=dict(
                                size=5,
                                color='rgba(255, 255, 0, .8)',
                                line=dict(
                                    width=1,
                                    color='rgb(0, 0, 0, 1)'
                                )
                            )
                        )
                    ],
                    'layout': go.Layout(
                        title='Made & Missed Shots',
                        showlegend=True,
                        xaxis=dict(
                            showgrid=False,
                            range=[-300, 300]
                        ),
                        yaxis=dict(
                            showgrid=False,
                            range=[-100, 500]
                        ),
                        height=600,
                        width=650,
                        shapes=court_plot()
                    )
                }
            )
        )


def division_image_header(conf, float, align):
    return html.Div(
        [dcc.Link(
            html.Img(src=teams.loc[teams['TeamID'] == i['TeamID'], 'TeamLogo'].iloc[0],
                     style={'height': 'auto', 'width': '75px'},
                     className='team-overlay',
                     id='team-logo-' + str(i['TeamID'])),
            href='/team/' + str(i['TeamID']),
            style={'padding-{}'.format(align): '20px'})
            for i in teams.sort_values(by=['Division', 'TeamCode']).to_dict('records') if
            i['TeamID'] is not None and i['Conference'] == conf],
        style={'float': float, 'width': '50%', 'text-align': align, 'padding': '0px 0px 0px 0px'}
    )


def team_stats_graph(team_id, value, option, metric, season):
    if team_id and value in ['Current Roster', 'Stats']:
        if option == 'Compare':
            query = '{}'.format(team_season_stats_query)
            team_stats = load_data(query, sql_config, 'nba', TEAM_STATS_COLUMNS).sort_values(by=metric)
            temp = team_stats[team_stats['season'] == season]
            data_x = temp['teamcode'].values.tolist()
            data_y = temp[metric].values.tolist()

        elif option == 'Trend':
            query = '{} {}'.format(team_season_stats_query, team_id)
            team_stats = load_data(query, sql_config, 'nba', TEAM_STATS_COLUMNS).sort_values(by='season')
            data_x = [str(i) for i in team_stats['season'].values.tolist()]
            data_y = team_stats[metric].values.tolist()

        return {
            'data': [
                {'x': data_x, 'y': data_y, 'type': 'bar', 'name': '{}'.format(TEAMS[team_id]['name'])}
            ],
            'layout': {
                'title': 'Team: {0} \n Metric: {1}'.format(TEAMS[team_id]['name'], metric)
            }
        }

    else:
        return {
            'data': [
                {'x': 0, 'y': 0, 'type': 'bar'}
            ],
            'layout': {
                'title': 'Select a team to get started'
            }
        }


rosters = load_data(team_roster_query, sql_config, 'nba', CURRENT_ROSTER_COLUMNS)
team_df = current_roster(rosters)

teams = load_data(team_query, sql_config, 'nba', TEAM_COLUMNS)


def update_layout():
    return html.Div(
        children=[
            dcc.Location(id='team_url', refresh=False),

            html.Div(
                children=[
                    division_image_header('Eastern', 'left', 'right'),
                    division_image_header('Western', 'right', 'left')
                ],
                style={'display': 'flex'}
            ),

            html.Div(
                children=[
                    dcc.Tabs(id="div-tabs", value='Current Roster', children=[
                        dcc.Tab(label='ROSTER', value='Current Roster', style=SINGLE_TAB_STYLE,
                                selected_style=SELECTED_TAB_STYLE),
                        dcc.Tab(label='RESULTS', value='Results',
                                style=SINGLE_TAB_STYLE, selected_style=SELECTED_TAB_STYLE),
                        dcc.Tab(label='STATS', value='Stats',
                                style=SINGLE_TAB_STYLE, selected_style=SELECTED_TAB_STYLE),
                        dcc.Tab(label='SHOTS', value='Shots',
                                style=SINGLE_TAB_STYLE, selected_style=SELECTED_TAB_STYLE)],
                             style=ALL_TAB_STYLE
                             )
                ]
            ),

            html.P('Select TREND to view team stats over time or COMPARE to see stats relative to the league',
                   style={'font-size': '12px'}
                   ),

            dcc.RadioItems(
                id='stat-option',
                options=[
                    {'label': 'TREND', 'value': 'Trend'},
                    {'label': 'COMPARE', 'value': 'Compare'}
                ],
                value='Trend',
                labelStyle={'display': 'inline-block'}
            ),

            dcc.RadioItems(
                id='season-option',
                options=[{'label': i, 'value': i} for i in
                         ['2014-2015', '2015-2016', '2016-2017', '2017-2018', '2018-2019', '2019-2020']],
                value='2019-2020',
                labelStyle={'display': 'inline-block'}
            ),

            dcc.Dropdown(
                id='metric-picker',
                options=[{'label': i, 'value': i} for i in TEAM_STATS_COLUMNS if
                         i not in ['tid', 'teamcode', 'season']],
                value='ast'
            ),

            dcc.Loading(
                id="loading-1",
                children=[html.Div(
                    dcc.Graph(id='team-graph', style={'width': '100%'})
                )],
                type="default"
            ),

            dcc.Loading(
                id="loading-2",
                children=html.Div(
                    id='team_roster_container'
                ),
                type="default"
            ),

            html.Div(
                id='shot_plot'
            )

        ])


app.layout = update_layout()


@app.callback(
    Output('team_roster_container', 'children'),
    [Input('team_url', 'pathname'),
     Input('div-tabs', 'value')]
)
def update_team_roster_table(pathname, value):
    if pathname:
        team_id = pathname.split('/')[-1]
    else:
        return html.P('Select a team to get started')

    if value == 'Current Roster':
        _teamdf = current_roster(rosters, team_id)
        return build_table(_teamdf, 'Summary')

    elif value == 'Results':
        return html.P('Results')

    elif value == 'Shots':
        return html.P('Shots')


@app.callback(
    Output('team-graph', 'figure'),
    [Input('team_url', 'pathname'),
     Input('div-tabs', 'value'),
     Input('stat-option', 'value'),
     Input('metric-picker', 'value'),
     Input('season-option', 'value')]
)
def team_summary_stats(pathname, value, option, metric, season):
    team_id = pathname.split('/')[-1] if pathname else None

    return team_stats_graph(team_id, value, option, metric, season)


@app.callback(
    Output('shot_plot', 'figure'),
    [Input('team_url', 'pathname')]
)
def update_shot_plot(pathname):
    if pathname:
        if pathname.split('/')[1] == 'player':
            player_id = pathname.split('/')[-1]
        else:
            return html.P('SELECT A TEAM ABOVE TO GET STARTED', style={'float': 'center'})

        player_df = get_shots(player_id)

        return shot_map(player_df)


@server.route('/login')
def login():
    callback = url_for('authorized', _external=True)
    return google.authorize(callback=callback)


if __name__ == '__main__':
    app.run_server(debug=True)

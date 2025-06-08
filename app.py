import dash
from dash import dcc, html, Input, Output, State, callback
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import dash_bootstrap_components as dbc
import openai
import os
import requests


# Initialize the Dash app
app = dash.Dash(__name__)
app.title = "3D Printing Construction Database"

# PRODUCTION: Updated API key loading for deployment
def load_api_key():
    try:
        # First try environment variable (for production)
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            return api_key
        # Fallback to file (for local development)
        with open('API.txt', 'r') as f:
            return f.read().strip()
    except:
        return None

# Load data
def load_data():
    try:
        df = pd.read_csv('projects.csv')
        df = df.copy()
        df = df.dropna(subset=['Project', 'Year', 'Country', 'Material', 'Organization'])
        df['Year'] = pd.to_numeric(df['Year'], errors='coerce')
        df = df.dropna(subset=['Year'])
        df = df.reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

# Categorize materials
def categorize_material(material):
    material_lower = str(material).lower()
    if any(term in material_lower for term in ['concrete', 'cement']):
        return 'Concrete/Cement'
    elif any(term in material_lower for term in ['ceramic', 'clay']):
        return 'Ceramics/Clay'
    elif 'composite' in material_lower:
        return 'Composite'
    elif any(term in material_lower for term in ['plastic', 'polymer']):
        return 'Plastic/Polymer'
    elif 'metal' in material_lower:
        return 'Metal'
    else:
        return 'Other/Experimental'

# Parse natural language filter commands
def parse_filter_command(message):
    """Parse user message for filter commands"""
    message_lower = message.lower()
    commands = {}
    
    # Material filters
    material_mappings = {
        'concrete': 'Concrete/Cement',
        'cement': 'Concrete/Cement',
        'ceramic': 'Ceramics/Clay',
        'clay': 'Ceramics/Clay',
        'composite': 'Composite',
        'plastic': 'Plastic/Polymer',
        'polymer': 'Plastic/Polymer',
        'metal': 'Metal',
        'experimental': 'Other/Experimental'
    }
    
    for keyword, category in material_mappings.items():
        if keyword in message_lower:
            commands['material'] = category
            break
    
    # Year filters
    import re
    range_patterns = [
        r'(?:from|between)\s+(\d{4})\s+(?:to|and)\s+(\d{4})',
        r'(\d{4})\s*[-–]\s*(\d{4})',
        r'(\d{4})\s+to\s+(\d{4})'
    ]
    
    for pattern in range_patterns:
        range_match = re.search(pattern, message_lower)
        if range_match:
            start_year = int(range_match.group(1))
            end_year = int(range_match.group(2))
            commands['year_range'] = [min(start_year, end_year), max(start_year, end_year)]
            break
    
    if 'year_range' not in commands:
        year_matches = re.findall(r'\b(20[0-9]{2}|19[0-9]{2})\b', message)
        if len(year_matches) >= 2:
            years = [int(y) for y in year_matches[:2]]
            commands['year_range'] = [min(years), max(years)]
        elif len(year_matches) == 1:
            year = int(year_matches[0])
            commands['year_range'] = [year, year]
    
    # Reset command
    reset_keywords = ['reset', 'clear', 'all projects', 'show all', 'remove filters', 'no filter']
    if any(keyword in message_lower for keyword in reset_keywords):
        commands['reset'] = True
    
    return commands

# Load data
df = load_data()
if not df.empty:
    df = df.copy()
    df['Material_Category'] = df['Material'].apply(categorize_material)

# Layout
app.layout = html.Div([
    # Full-window background map
    html.Div([
        dcc.Graph(
            id='world-map',
            style={
                'height': '100vh',
                'width': '100vw',
                'position': 'absolute',
                'top': '0',
                'left': '0',
                'z-index': '1'
            },
            config={'displayModeBar': False}
        )
    ]),
    
    # Floating header with 20% transparency
    html.Div([
        html.H1("(beta) AI Powered 3D Printing Construction Database", style={
            'margin': '0',
            'font-size': '22px',
            'font-weight': 'bold',
            'font-family': 'Arial, sans-serif',
            'color': '#333333',
            'text-align': 'center',
            'padding': '15px'
        })
    ], style={
        'position': 'absolute',
        'top': '10px',
        'left': '50%',
        'transform': 'translateX(-50%)',
        'background-color': 'rgba(255, 255, 255, 0.2)',
        'border-radius': '10px',
        'box-shadow': '0 4px 15px rgba(0,0,0,0.1)',
        'z-index': '10',
        'backdrop-filter': 'blur(10px)'
    }),
    
    # About Platform and Data Collection buttons - Top Left
    html.Div([
        html.Button("About the Platform", id="about-platform-btn", style={
            'padding': '8px 16px',
            'background-color': '#f8f9fa',
            'color': '#333',
            'border': '1px solid #ddd',
            'border-radius': '6px',
            'font-size': '12px',
            'font-weight': 'bold',
            'cursor': 'pointer',
            'font-family': 'Arial, sans-serif',
            'box-shadow': '0 2px 8px rgba(0,0,0,0.15)',
            'transition': 'background-color 0.3s ease',
            'margin-right': '8px'
        }),
        html.Button("Data Collection", id="data-collection-btn", style={
            'padding': '8px 16px',
            'background-color': '#f8f9fa',
            'color': '#333',
            'border': '1px solid #ddd',
            'border-radius': '6px',
            'font-size': '12px',
            'font-weight': 'bold',
            'cursor': 'pointer',
            'font-family': 'Arial, sans-serif',
            'box-shadow': '0 2px 8px rgba(0,0,0,0.15)',
            'transition': 'background-color 0.3s ease'
        })
    ], style={
        'position': 'absolute',
        'top': '10px',
        'left': '20px',
        'z-index': '10',
        'display': 'flex',
        'align-items': 'center'
    }),
    
    # Floating left sidebar
    html.Div([
        # Search Projects
        html.Div([
            html.Label("Search Projects", style={
                'font-size': '12px',
                'font-weight': 'bold',
                'margin-bottom': '5px',
                'font-family': 'Arial, sans-serif',
                'color': '#333'
            }),
            html.Div([
                dcc.Input(
                    id='search-input',
                    type='text',
                    placeholder='Search projects, organizations, locations...',
                    style={
                        'width': '100%',
                        'padding': '6px 25px 6px 8px',
                        'border': 'none',
                        'border-radius': '4px',
                        'font-size': '11px',
                        'box-sizing': 'border-box'
                    }
                ),
                html.Button("×", id="clear-search", style={
                    'position': 'absolute',
                    'right': '5px',
                    'top': '50%',
                    'transform': 'translateY(-50%)',
                    'background': 'none',
                    'border': 'none',
                    'font-size': '14px',
                    'color': '#999',
                    'cursor': 'pointer',
                    'padding': '2px',
                    'width': '16px',
                    'height': '16px',
                    'display': 'flex',
                    'align-items': 'center',
                    'justify-content': 'center',
                    'border-radius': '50%'
                }, **{'data-testid': 'clear-search'})
            ], style={
                'position': 'relative', 
                'margin-bottom': '15px',
                'width': '100%'
            })
        ]),
        
        # Filter by Material
        html.Div([
            html.Label("Filter by Material", style={
                'font-size': '12px',
                'font-weight': 'bold',
                'margin-bottom': '5px',
                'font-family': 'Arial, sans-serif',
                'color': '#333'
            }),
            dcc.Dropdown(
                id='material-filter',
                options=[{'label': 'All', 'value': 'all'}] + 
                       [{'label': mat, 'value': mat} for mat in df['Material_Category'].unique()] if not df.empty else [],
                value='all',
                style={
                    'font-size': '11px', 
                    'margin-bottom': '15px',
                    'border': 'none'
                }
            )
        ]),
        
        # Filter by Year
        html.Div([
            html.Label("Filter by Year", style={
                'font-size': '12px',
                'font-weight': 'bold',
                'margin-bottom': '5px',
                'font-family': 'Arial, sans-serif',
                'color': '#333'
            }),
            dcc.RangeSlider(
                id='year-filter',
                min=int(df['Year'].min()) if not df.empty else 2015,
                max=int(df['Year'].max()) if not df.empty else 2025,
                step=1,
                value=[int(df['Year'].min()), int(df['Year'].max())] if not df.empty else [2015, 2025],
                marks={
                    int(df['Year'].min()) if not df.empty else 2015: {'label': str(int(df['Year'].min())) if not df.empty else '2015', 'style': {'font-size': '9px', 'color': '#333'}},
                    int(df['Year'].max()) if not df.empty else 2025: {'label': str(int(df['Year'].max())) if not df.empty else '2025', 'style': {'font-size': '9px', 'color': '#333'}}
                },
                tooltip={"placement": "bottom", "always_visible": True}
            )
        ], style={'margin-bottom': '20px'}),
        
        # Project list
        html.Div([
            html.Label("Projects", style={
                'font-size': '12px',
                'font-weight': 'bold',
                'margin-bottom': '8px',
                'font-family': 'Arial, sans-serif',
                'color': '#333',
                'display': 'block'
            }),
            html.Div(id='project-list', style={
                'height': '150px',
                'overflow-y': 'auto',
                'background-color': 'rgba(255, 255, 255, 0.9)',
                'border-radius': '5px',
                'padding': '8px',
                'font-size': '11px',
                'font-family': 'Arial, sans-serif'
            })
        ], style={'margin-bottom': '20px'}),
        
        # AI Assistant
        html.Div([
            html.Label("💬 AI Assistant", style={
                'font-size': '12px',
                'font-weight': 'bold',
                'margin-bottom': '5px',
                'font-family': 'Arial, sans-serif',
                'color': '#333',
                'display': 'block'
            }),
            html.P("GPT-3.5 powered assistant trained on 3D printing construction data. Ask questions or apply filters!", style={
                'font-size': '9px',
                'color': '#666',
                'margin-bottom': '8px',
                'font-family': 'Arial, sans-serif',
                'font-style': 'italic'
            }),
            html.Div(id='chat-display', style={
                'height': '80px',
                'overflow-y': 'auto',
                'background-color': 'rgba(255, 255, 255, 0.9)',
                'border-radius': '5px',
                'padding': '8px',
                'margin-bottom': '8px',
                'font-size': '10px',
                'font-family': 'Arial, sans-serif'
            }),
            html.Div([
                dcc.Input(
                    id='chat-input',
                    type='text',
                    placeholder='Try: "show concrete projects" or "filter 2020-2023"',
                    style={
                        'width': '60%',
                        'padding': '6px',
                        'border': '1px solid #ddd',
                        'border-radius': '3px',
                        'font-size': '10px',
                        'margin-right': '5px',
                        'vertical-align': 'top'
                    }
                ),
                html.Button('Send', id='chat-send', style={
                    'width': '35%',
                    'padding': '6px',
                    'background-color': '#007bff',
                    'color': 'white',
                    'border': 'none',
                    'border-radius': '3px',
                    'font-size': '10px',
                    'cursor': 'pointer',
                    'vertical-align': 'top'
                })
            ], style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '8px'})
        ])
    ], style={
        'position': 'absolute',
        'top': '70px',
        'left': '20px',
        'width': '300px',
        'background-color': 'rgba(248, 248, 248, 0.95)',
        'border-radius': '15px',
        'padding': '20px',
        'box-shadow': '0 8px 25px rgba(0,0,0,0.15)',
        'z-index': '10',
        'backdrop-filter': 'blur(10px)',
        'border': '1px solid rgba(255,255,255,0.2)'
    }),
    
    # Floating timeline at bottom
    html.Div([
        dcc.Graph(
            id='timeline-chart',
            style={'height': '120px', 'width': '100%'},
            config={'displayModeBar': False}
        )
    ], style={
        'position': 'absolute',
        'bottom': '20px',
        'left': '360px',
        'right': '20px',
        'background-color': 'rgba(0, 0, 0, 0)',
        'border-radius': '0px',
        'padding': '0px',
        'box-shadow': 'none',
        'z-index': '10',
        'backdrop-filter': 'none'
    }),
    
    # Project details side panel
    html.Div([
        html.Div([
            # Close button
            html.Button("✕", id="close-panel", style={
                'position': 'absolute',
                'top': '15px',
                'right': '15px',
                'background': 'none',
                'border': 'none',
                'font-size': '20px',
                'cursor': 'pointer',
                'color': '#333'
            }),
            
            # Panel content
            html.Div(id='panel-content', style={
                'padding': '20px',
                'padding-top': '50px'
            })
        ], style={
            'width': '400px',
            'height': '100vh',
            'background-color': 'rgba(255, 255, 255, 0.95)',
            'backdrop-filter': 'blur(10px)',
            'border-left': '1px solid rgba(0,0,0,0.1)',
            'overflow-y': 'auto'
        })
    ], id='project-panel', style={
        'position': 'fixed',
        'top': '0',
        'right': '-400px',
        'z-index': '1001',
        'transition': 'right 0.3s ease-in-out',
        'height': '100vh'
    }),
    
    # About panel (for Data Collection & Platform info)
    html.Div([
        html.Div([
            # Close button
            html.Button("✕", id="close-about-panel", style={
                'position': 'absolute',
                'top': '15px',
                'right': '15px',
                'background': 'none',
                'border': 'none',
                'font-size': '20px',
                'cursor': 'pointer',
                'color': '#333'
            }),
            
            # Panel content
            html.Div(id='about-panel-content', style={
                'padding': '20px',
                'padding-top': '50px'
            })
        ], style={
            'width': '500px',
            'height': '100vh',
            'background-color': 'rgba(255, 255, 255, 0.95)',
            'backdrop-filter': 'blur(10px)',
            'border-left': '1px solid rgba(0,0,0,0.1)',
            'overflow-y': 'auto'
        })
    ], id='about-panel', style={
        'position': 'fixed',
        'top': '0',
        'right': '-500px',
        'z-index': '1002',
        'transition': 'right 0.3s ease-in-out',
        'height': '100vh'
    }),
    
    # Hidden divs for state storage
    html.Div(id='chat-history-store', style={'display': 'none'}),
    html.Div(id='current-open-project', style={'display': 'none'}, children=""),
    html.Div(id='current-about-section', style={'display': 'none'}, children="")
], style={
    'font-family': 'Arial, sans-serif',
    'margin': '0',
    'padding': '0',
    'height': '100vh',
    'overflow': 'hidden'
})

# Clear search callback
@app.callback(
    Output('search-input', 'value'),
    [Input('clear-search', 'n_clicks')],
    prevent_initial_call=True
)
def clear_search(n_clicks):
    if n_clicks:
        return ""
    return dash.no_update

# Dashboard update callback with search functionality
@app.callback(
    [Output('world-map', 'figure'),
     Output('timeline-chart', 'figure'),
     Output('project-list', 'children')],
    [Input('material-filter', 'value'),
     Input('year-filter', 'value'),
     Input('search-input', 'value')]
)
def update_dashboard(material_filter, year_range, search_term):
    if df.empty:
        return {}, {}, "No data available"
    
    # Filter data by year and material
    filtered_df = df.loc[
        (df['Year'] >= year_range[0]) & 
        (df['Year'] <= year_range[1])
    ].copy()
    
    if material_filter != 'all':
        filtered_df = filtered_df.loc[filtered_df['Material_Category'] == material_filter].copy()
    
    # Apply search filter if search term exists
    if search_term:
        search_term = search_term.lower()
        search_mask = (
            filtered_df['Project'].str.lower().str.contains(search_term, na=False) |
            filtered_df['Organization'].str.lower().str.contains(search_term, na=False) |
            filtered_df['Country'].str.lower().str.contains(search_term, na=False) |
            filtered_df['City'].str.lower().str.contains(search_term, na=False) |
            filtered_df['Material'].str.lower().str.contains(search_term, na=False)
        )
        filtered_df = filtered_df.loc[search_mask].copy()
    
    # Full-window map
    if len(filtered_df) > 0 and 'Latitude' in filtered_df.columns:
        map_fig = go.Figure()
        
        # Updated tooltip order: Project → Organization → Location → Material → Year
        tooltip_text = (filtered_df['Project'] + '<br>' + 
                       filtered_df['Organization'] + '<br>' +
                       filtered_df['City'] + ', ' + filtered_df['Country'] + '<br>' +
                       'Material: ' + filtered_df['Material_Category'] + '<br>' +
                       'Year: ' + filtered_df['Year'].astype(int).astype(str))
        
        map_fig.add_trace(go.Scattergeo(
            lon=filtered_df['Longitude'],
            lat=filtered_df['Latitude'],
            mode='markers',
            marker=dict(
                size=10,
                color='black',
                opacity=0.8,
                line=dict(width=1, color='white')
            ),
            text=tooltip_text,
            hovertemplate='%{text}<extra></extra>',
            showlegend=False,
            customdata=filtered_df['Project'].values,
            name='projects'
        ))
        
        map_fig.update_layout(
            geo=dict(
                projection_type='natural earth',
                showland=True,
                landcolor='rgb(245,245,245)',
                showocean=True,
                oceancolor='rgb(255,255,255)',
                showlakes=True,
                lakecolor='rgb(255,255,255)',
                showrivers=False,
                showcountries=True,
                countrycolor='rgb(220,220,220)',
                coastlinecolor='rgb(220,220,220)',
                showframe=False,
                showcoastlines=True
            ),
            margin=dict(l=0, r=0, t=0, b=0),
            height=None,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
    else:
        map_fig = go.Figure()
        map_fig.update_layout(
            height=None,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=0, b=0)
        )
    
    # Timeline chart
    if len(filtered_df) > 0:
        timeline_data = filtered_df.groupby('Year').size().reset_index(name='Count')
        timeline_fig = go.Figure()
        timeline_fig.add_trace(go.Scatter(
            x=timeline_data['Year'],
            y=timeline_data['Count'],
            mode='lines+markers',
            line=dict(color='black', width=2),
            marker=dict(color='black', size=4),
            showlegend=False
        ))
        timeline_fig.update_layout(
            margin=dict(l=0, r=0, t=5, b=20),
            height=120,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                showgrid=False,
                showline=False,
                title='',
                tickfont=dict(size=9, color='#333'),
                color='#333'
            ),
            yaxis=dict(
                showgrid=False,
                showticklabels=False,
                showline=False,
                title='',
                visible=False
            )
        )
    else:
        timeline_fig = go.Figure()
        timeline_fig.update_layout(
            height=120,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=5, b=20)
        )
    
    # Project list
    if len(filtered_df) > 0:
        project_items = []
        for idx, row in filtered_df.iterrows():
            project_items.append(
                html.Div([
                    html.Div(
                        row['Project'], 
                        id=f'project-link-{idx}',
                        style={
                            'font-weight': 'bold',
                            'color': '#0066cc',
                            'cursor': 'pointer',
                            'margin-bottom': '2px'
                        },
                        className='project-link',
                        **{'data-project-index': idx}
                    ),
                    html.Div(f"{row['Organization']}", style={
                        'color': '#666',
                        'font-size': '9px'
                    }),
                    html.Div(f"{row['Year']} • {row['City']}, {row['Country']}", style={
                        'color': '#888',
                        'font-size': '8px'
                    })
                ], style={
                    'padding': '6px 8px',
                    'margin-bottom': '2px',
                    'border-radius': '3px',
                    'cursor': 'pointer',
                    'transition': 'background-color 0.2s'
                }, 
                className='project-item',
                id={'type': 'project-item', 'index': idx, 'project_name': row['Project']},
                n_clicks=0
                )
            )
        project_list = project_items
    else:
        project_list = [html.Div("No projects match the current filters", style={'color': '#888', 'font-style': 'italic'})]
    
    return map_fig, timeline_fig, project_list

# UNIFIED Project panel callback - handles both sidebar clicks AND map clicks!
@app.callback(
    [Output('project-panel', 'style'),
     Output('panel-content', 'children'),
     Output('current-open-project', 'children')],
    [Input({'type': 'project-item', 'index': dash.dependencies.ALL, 'project_name': dash.dependencies.ALL}, 'n_clicks'),
     Input('world-map', 'clickData'),
     Input('close-panel', 'n_clicks')],
    [State('project-panel', 'style'),
     State('current-open-project', 'children')]
)
def toggle_project_panel(project_clicks, map_click_data, close_clicks, current_style, current_open_project):
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return current_style, "", ""
    
    trigger_id = ctx.triggered[0]['prop_id']
    clicked_project_name = None
    
    # Close panel button clicked
    if 'close-panel' in trigger_id:
        return {**current_style, 'right': '-400px'}, "", ""
    
    # MAP DOT CLICKED
    if 'world-map.clickData' in trigger_id and map_click_data:
        try:
            clicked_project_name = map_click_data['points'][0]['customdata']
        except (KeyError, IndexError, TypeError):
            return current_style, "", current_open_project
    
    # SIDEBAR PROJECT CLICKED
    elif project_clicks and any(project_clicks):
        for i, clicks in enumerate(project_clicks):
            if clicks and clicks > 0:
                trigger_info = ctx.triggered[0]['prop_id']
                import json
                if '"project_name":"' in trigger_info:
                    start = trigger_info.find('"project_name":"') + len('"project_name":"')
                    end = trigger_info.find('"', start)
                    clicked_project_name = trigger_info[start:end]
                break
    
    # Process the clicked project
    if clicked_project_name and not df.empty:
        try:
            # TOGGLE FUNCTIONALITY
            if clicked_project_name == current_open_project:
                return {**current_style, 'right': '-400px'}, "", ""
            
            # Find project by name
            project_data = df[df['Project'] == clicked_project_name].iloc[0]
            
            # Create panel content
            panel_content = html.Div([
                html.H3(project_data['Project'], style={
                    'color': '#333',
                    'margin-bottom': '20px',
                    'font-size': '20px',
                    'font-weight': 'bold',
                    'line-height': '1.3'
                }),
                
                html.Div([
                    html.Strong("Description:", style={'color': '#333', 'font-size': '14px'}),
                    html.P(
                        project_data.get('Descrtiption', project_data.get('Description', 'No description available')), 
                        style={
                            'color': '#555', 
                            'margin-top': '8px', 
                            'line-height': '1.5',
                            'font-size': '13px'
                        }
                    )
                ], style={'margin-bottom': '25px'}),
                
                html.Div([
                    html.Div([
                        html.Strong("Organization:", style={'color': '#333', 'font-size': '12px'}),
                        html.P(project_data['Organization'], style={'color': '#555', 'margin-top': '5px', 'font-size': '12px'})
                    ], style={'margin-bottom': '15px'}),
                    
                    html.Div([
                        html.Strong("Year:", style={'color': '#333', 'font-size': '12px'}),
                        html.P(str(int(project_data['Year'])), style={'color': '#555', 'margin-top': '5px', 'font-size': '12px'})
                    ], style={'margin-bottom': '15px'}),
                    
                    html.Div([
                        html.Strong("Location:", style={'color': '#333', 'font-size': '12px'}),
                        html.P(f"{project_data['City']}, {project_data['Country']}", 
                               style={'color': '#555', 'margin-top': '5px', 'font-size': '12px'})
                    ], style={'margin-bottom': '15px'}),
                    
                    html.Div([
                        html.Strong("Material:", style={'color': '#333', 'font-size': '12px'}),
                        html.P(project_data['Material'], style={'color': '#555', 'margin-top': '5px', 'font-size': '12px'})
                    ], style={'margin-bottom': '25px'}),
                    
                    html.Div([
                        html.Strong("Project Website:", style={'color': '#333', 'font-size': '12px'}),
                        html.Br(),
                        html.A("🔗 Visit Project Page", 
                               href=project_data.get('Link', '#'),
                               target="_blank",
                               style={
                                   'color': '#0066cc', 
                                   'text-decoration': 'none', 
                                   'margin-top': '8px', 
                                   'display': 'inline-block',
                                   'font-size': '12px',
                                   'padding': '8px 12px',
                                   'border': '1px solid #0066cc',
                                   'border-radius': '4px',
                                   'background-color': '#f8f9fa'
                               })
                        if project_data.get('Link') else html.P("No website available", style={'color': '#999', 'margin-top': '8px', 'font-style': 'italic', 'font-size': '12px'})
                    ])
                ])
            ])
            
            return {**current_style, 'right': '0px'}, panel_content, clicked_project_name
            
        except Exception as e:
            error_content = html.Div([
                html.H4("Error Loading Project", style={'color': '#d32f2f'}),
                html.P(f"Unable to load project details: {str(e)}", style={'color': '#666'})
            ])
            return {**current_style, 'right': '0px'}, error_content, clicked_project_name
    
    return current_style, "", current_open_project

# About panel callback
@app.callback(
    [Output('about-panel', 'style'),
     Output('about-panel-content', 'children'),
     Output('current-about-section', 'children')],
    [Input('about-platform-btn', 'n_clicks'),
     Input('data-collection-btn', 'n_clicks'),
     Input('close-about-panel', 'n_clicks')],
    [State('about-panel', 'style'),
     State('current-about-section', 'children')]
)
def toggle_about_panel(platform_clicks, data_clicks, close_clicks, current_style, current_section):
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return current_style, "", ""
    
    trigger_id = ctx.triggered[0]['prop_id']
    
    # Close panel button clicked
    if 'close-about-panel' in trigger_id:
        return {**current_style, 'right': '-500px'}, "", ""
    
    # About Platform button clicked
    if 'about-platform-btn' in trigger_id and platform_clicks:
        # Toggle: if same section is open, close it
        if current_section == "about-platform":
            return {**current_style, 'right': '-500px'}, "", ""
        
        # Create About Platform content
        content = html.Div([
            html.H2("Building the Platform", style={
                'color': '#333',
                'margin-bottom': '20px',
                'font-size': '24px',
                'font-weight': 'bold'
            }),
            html.H3("How The 3D Printing Construction Dashboard Is Built", style={
                'color': '#555',
                'margin-bottom': '20px',
                'font-size': '18px',
                'font-weight': 'normal'
            }),
            
            html.P("Note: This is a passion project that continuously tracks additive manufacturing in construction. While it aims to provide valuable insights into industry trends, it should not be used as a sole source of data or for critical decision-making.", style={
                'margin-bottom': '20px',
                'line-height': '1.6',
                'font-size': '13px',
                'color': '#666',
                'font-style': 'italic',
                'padding': '10px',
                'background-color': '#f8f9fa',
                'border-radius': '5px'
            }),
            
            html.P("This platform transforms raw construction project data into actionable insights through a technical architecture built entirely using Python (with loads of help from Claude) without any visual UI. This approach was chosen to avoid paid platforms while maintaining professional functionality. Here's how it works:", style={
                'margin-bottom': '20px',
                'line-height': '1.6',
                'font-size': '14px'
            }),
            
            html.Div([
                html.H4("Frontend Framework:", style={'color': '#333', 'font-size': '14px', 'margin-bottom': '8px'}),
                html.P("Built on Plotly Dash with a full-window world map, floating control panels, and real-time data visualization that updates as users apply filters by materials, years, and regions.", style={'margin-bottom': '15px', 'line-height': '1.5', 'font-size': '13px'})
            ]),
            
            html.Div([
                html.H4("Data Visualization:", style={'color': '#333', 'font-size': '14px', 'margin-bottom': '8px'}),
                html.P("Project coordinates become interactive map markers, with timeline charts showing industry patterns over time. Users can filter data and see results instantly across all visualizations.", style={'margin-bottom': '15px', 'line-height': '1.5', 'font-size': '13px'})
            ]),
            
            html.Div([
                html.H4("AI Assistant:", style={'color': '#333', 'font-size': '14px', 'margin-bottom': '8px'}),
                html.P("A GPT-3.5-turbo chatbot understands commands like \"show concrete projects from 2020-2023\" and applies the appropriate filters. It maintains awareness of what data is currently being viewed.", style={'margin-bottom': '15px', 'line-height': '1.5', 'font-size': '13px'})
            ]),
            
            html.Div([
                html.H4("Technical Implementation:", style={'color': '#333', 'font-size': '14px', 'margin-bottom': '8px'}),
                html.P("Python handles data processing with pandas, manages user interactions through Dash callbacks, and maintains chat history and panel states.", style={'margin-bottom': '15px', 'line-height': '1.5', 'font-size': '13px'})
            ])
        ])
        
        return {**current_style, 'right': '0px'}, content, "about-platform"
    
    # Data Collection button clicked
    if 'data-collection-btn' in trigger_id and data_clicks:
        # Toggle: if same section is open, close it
        if current_section == "data-collection":
            return {**current_style, 'right': '-500px'}, "", ""
        
        # Create Data Collection content
        content = html.Div([
            html.H2("Data Collection", style={
                'color': '#333',
                'margin-bottom': '20px',
                'font-size': '24px',
                'font-weight': 'bold'
            }),
            html.H3("How 3D Printing Construction Projects Are Collected", style={
                'color': '#555',
                'margin-bottom': '20px',
                'font-size': '18px',
                'font-weight': 'normal'
            }),
            
            html.P("Note: This is a passion project that continuously tracks additive manufacturing in construction. While it aims to provide valuable insights into industry trends, it should not be used as a sole source of data or for critical decision-making.", style={
                'margin-bottom': '20px',
                'line-height': '1.6',
                'font-size': '13px',
                'color': '#666',
                'font-style': 'italic',
                'padding': '10px',
                'background-color': '#f8f9fa',
                'border-radius': '5px'
            }),
            
            html.P("This database tracks 3D printing construction projects from around the world. Here's how it works:", style={
                'margin-bottom': '20px',
                'line-height': '1.6',
                'font-size': '14px'
            }),
            
            html.Div([
                html.H4("Source Data:", style={'color': '#333', 'font-size': '14px', 'margin-bottom': '8px'}),
                html.P("Projects are initially added from URLs sourced from a manually curated database that was previously assembled, largely based on RSS feeds. This existing collection serves as the foundation for automated processing and analysis.", style={'margin-bottom': '15px', 'line-height': '1.5', 'font-size': '13px'})
            ]),
            
            html.Div([
                html.H4("Automated Data Extraction:", style={'color': '#333', 'font-size': '14px', 'margin-bottom': '8px'}),
                html.P("A Python-based system automatically visits each URL and extracts key information: project names, completion years, materials used, locations, and the organizations behind them, rather than requiring manual data entry for each project. This process is designed with respect for website policies, using reasonable delays between requests, honoring robots.txt files, and focusing only on publicly available information about projects, largely based on RSS feeds.", style={'margin-bottom': '15px', 'line-height': '1.5', 'font-size': '13px'})
            ]),
            
            html.Div([
                html.H4("AI-Powered Understanding:", style={'color': '#333', 'font-size': '14px', 'margin-bottom': '8px'}),
                html.P("The system uses OpenAI's technology to \"read\" a snippet of each project webpage (to reduce costs and token usage), interpreting details like whether a project used concrete or metal, if it was built by a university or company, and where in the world it's located.", style={'margin-bottom': '15px', 'line-height': '1.5', 'font-size': '13px'})
            ]),
            
            html.Div([
                html.H4("Pattern Recognition & Key Player Identification:", style={'color': '#333', 'font-size': '14px', 'margin-bottom': '8px'}),
                html.P("As the system processes projects, it builds patterns to identify key players in the industry, tracks organizational preferences (like which materials different companies typically use), and maps emerging trends in 3D printing construction.", style={'margin-bottom': '15px', 'line-height': '1.5', 'font-size': '13px'})
            ]),
            
            html.Div([
                html.H4("Intelligent Project Discovery:", style={'color': '#333', 'font-size': '14px', 'margin-bottom': '8px'}),
                html.P("Using keywords and patterns learned from the existing database, the system monitors RSS feeds from construction industry publications, research institutions, and key organizations to automatically discover new relevant projects. This discovery process is largely based on RSS feeds, ensuring access to legitimately syndicated content. When potential projects are found but the system is unsure about their relevance, they are flagged for manual review.", style={'margin-bottom': '15px', 'line-height': '1.5', 'font-size': '13px'})
            ]),
            
            html.Div([
                html.H4("AI as a tool:", style={'color': '#333', 'font-size': '14px', 'margin-bottom': '8px'}),
                html.P("This hybrid approach tries to ensure comprehensive coverage while maintaining accuracy - automation handles clear matches while human oversight validates uncertain cases.", style={'margin-bottom': '15px', 'line-height': '1.5', 'font-size': '13px'})
            ]),
            
            html.Div([
                html.H4("Result:", style={'color': '#333', 'font-size': '14px', 'margin-bottom': '8px'}),
                html.P("A continuously-updating view of how 3D printing is transforming the construction industry, revealing key players, material trends, and geographic hotspots worldwide. Obviously, all results should be taken with a pinch of (printed) salt.", style={'margin-bottom': '15px', 'line-height': '1.5', 'font-size': '13px'})
            ])
        ])
        
        return {**current_style, 'right': '0px'}, content, "data-collection"
    
    return current_style, "", current_section

# Chat callback with filter control and dynamic analysis
@app.callback(
    [Output('chat-display', 'children'),
     Output('chat-input', 'value'),
     Output('material-filter', 'value'),
     Output('year-filter', 'value'),
     Output('chat-history-store', 'children')],
    [Input('chat-send', 'n_clicks'),
     Input('chat-input', 'n_submit')],
    [State('chat-input', 'value'),
     State('chat-display', 'children'),
     State('material-filter', 'value'),
     State('year-filter', 'value'),
     State('chat-history-store', 'children')]
)
def update_chat_with_filters(n_clicks, n_submit, message, current_chat, current_material, current_year_range, stored_history):
    if not (n_clicks or n_submit) or not message:
        return current_chat or [], "", current_material, current_year_range, stored_history
    
    try:
        # Parse filter commands
        filter_commands = parse_filter_command(message)
        
        # Update filters
        new_material = current_material
        new_year_range = current_year_range
        filter_applied = False
        filter_message = ""
        
        if 'reset' in filter_commands:
            new_material = 'all'
            new_year_range = [int(df['Year'].min()), int(df['Year'].max())] if not df.empty else [2015, 2025]
            filter_applied = True
            filter_message = "🔄 Filters reset! Showing all projects."
        else:
            if 'material' in filter_commands:
                new_material = filter_commands['material']
                filter_applied = True
            if 'year_range' in filter_commands:
                new_year_range = filter_commands['year_range']
                filter_applied = True
            
            if filter_applied:
                applied_filters = []
                if 'material' in filter_commands:
                    applied_filters.append(f"Material: {filter_commands['material']}")
                if 'year_range' in filter_commands:
                    applied_filters.append(f"Years: {filter_commands['year_range'][0]}-{filter_commands['year_range'][1]}")
                filter_message = f"🎯 Filters applied: {', '.join(applied_filters)}"
        
        # Get filtered data for AI context
        current_filtered = df.loc[
            (df['Year'] >= new_year_range[0]) & 
            (df['Year'] <= new_year_range[1])
        ].copy()
        if new_material != 'all':
            current_filtered = current_filtered.loc[current_filtered['Material_Category'] == new_material].copy()
        
        api_key = load_api_key()
        openai.api_key = api_key
        if not api_key:
            error_msg = "🤖 AI assistant unavailable (API key not found)"
            new_chat = (current_chat or []) + [
                html.Div([
                    html.B("You: ", style={'color': '#333'}),
                    html.Span(message, style={'color': '#555'})
                ], style={'margin-bottom': '3px', 'font-size': '9px'}),
                html.Div([
                    html.B("AI: ", style={'color': '#red'}),
                    html.Span(error_msg, style={'color': '#red'})
                ], style={'margin-bottom': '6px', 'font-size': '9px'})
            ]
            return new_chat, "", current_material, current_year_range, stored_history
        
    
        
        # Create data analysis for AI
        total_projects = len(current_filtered)
        
        # Material breakdown
        material_stats = current_filtered['Material_Category'].value_counts()
        material_analysis = []
        for material, count in material_stats.head(5).items():
            percentage = (count / total_projects * 100) if total_projects > 0 else 0
            material_analysis.append(f"{material}: {count} ({percentage:.0f}%)")
        
        # Country analysis
        country_stats = current_filtered['Country'].value_counts()
        country_analysis = []
        for country, count in country_stats.head(5).items():
            percentage = (count / total_projects * 100) if total_projects > 0 else 0
            country_analysis.append(f"{country}: {count} ({percentage:.0f}%)")
        
        # Year trend analysis
        year_stats = current_filtered['Year'].value_counts().sort_index()
        year_trend = "No clear trend"
        if len(year_stats) > 1:
            recent_years = year_stats.tail(3).mean() if len(year_stats) >= 3 else year_stats.iloc[-1]
            early_years = year_stats.head(3).mean() if len(year_stats) >= 3 else year_stats.iloc[0]
            if recent_years > early_years * 1.5:
                year_trend = "Growing rapidly in recent years"
            elif recent_years < early_years * 0.7:
                year_trend = "Declining in recent years"
            else:
                year_trend = "Steady activity over time"
        
        # Organization analysis
        org_stats = current_filtered['Organization'].value_counts()
        top_org = org_stats.index[0] if len(org_stats) > 0 else "None"
        top_org_count = org_stats.iloc[0] if len(org_stats) > 0 else 0
        
        # AI context
        data_context = f"""You are an expert 3D printing construction analyst. Be concise and helpful.

CURRENT DATASET ({total_projects} projects):
• Filter: {new_material if new_material != 'all' else 'All materials'} | Years: {new_year_range[0]}-{new_year_range[1]}

TOP MATERIALS: {'; '.join(material_analysis[:3])}
TOP COUNTRIES: {'; '.join(country_analysis[:3])}
TREND: {year_trend}
LEADING ORG: {top_org} ({top_org_count} projects)

Respond in 2-3 sentences max. Be direct and insightful."""
        
        # Chat history management
        if stored_history:
            try:
                history = eval(stored_history) if isinstance(stored_history, str) else stored_history
            except:
                history = []
        else:
            history = []
        
        history.append({"role": "user", "content": message})
        
        if len(history) > 6:
            history = history[-6:]
        
        # Prepare messages
        messages = [{"role": "system", "content": data_context}] + history
        
        if filter_applied:
            current_message = f"Filter applied: {filter_message}. {message}"
        else:
            current_message = message
        
        messages[-1] = {"role": "user", "content": current_message}
        
        # GPT-3.5-turbo via REST
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 150
            }
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            resp.raise_for_status()
            ai_response = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            ai_response = f"🚨 AI error: {e}"


        if len(history) > 6:
            history = history[-6:]
        
        if filter_applied:
            ai_response = f"{filter_message}\n\n{ai_response}"
        
        # Update chat display
        new_chat = (current_chat or []) + [
            html.Div([
                html.B("You: ", style={'color': '#333'}),
                html.Span(message, style={'color': '#555'})
            ], style={'margin-bottom': '3px', 'font-size': '9px'}),
            html.Div([
                html.B("AI: ", style={'color': '#0066cc'}),
                html.Span(ai_response, style={'color': '#333'})
            ], style={'margin-bottom': '6px', 'font-size': '9px'})
        ]
        
        if len(new_chat) > 20:
            new_chat = new_chat[-20:]
        
        return new_chat, "", new_material, new_year_range, str(history)
        
    except Exception as e:
        error_msg = f"🚨 AI error: {str(e)[:50]}..."
        new_chat = (current_chat or []) + [
            html.Div([
                html.B("You: ", style={'color': '#333'}),
                html.Span(message, style={'color': '#555'})
            ], style={'margin-bottom': '3px', 'font-size': '9px'}),
            html.Div([
                html.B("AI: ", style={'color': '#red'}),
                html.Span(error_msg, style={'color': '#red'})
            ], style={'margin-bottom': '6px', 'font-size': '9px'})
        ]
        return new_chat, "", current_material, current_year_range, stored_history

# CSS
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            .project-item:hover {
                background-color: rgba(0, 102, 204, 0.1) !important;
            }
            .project-link:hover {
                text-decoration: underline !important;
            }
            body {
                margin: 0;
                padding: 0;
                overflow: hidden;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# PRODUCTION: Updated for deployment
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8050)), debug=False)

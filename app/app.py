import pandas as pd
import streamlit as st
from streamlit_folium import folium_static 
import plotly.express as px
from PIL import Image
import folium
from rdflib import Graph, URIRef, Namespace, Literal
from rdflib.namespace import RDFS, SKOS
from rdflib.plugins.sparql import prepareQuery
import sys
from SPARQLWrapper import SPARQLWrapper, JSON

#--- general webpage info
st.set_page_config(page_title='Air Quality')
st.header('Results for january - february 2021')
st.subheader('Choose your filters')

#loads ttl data
rdf_storage = "https://raw.githubusercontent.com/javipmontes/Group26/master/rdf/output-with-links.ttl"
g = Graph()
g.parse(rdf_storage, format="ttl", encoding="utf-8")

base = Namespace("http://www.group26.org/AP/ontology/AirPolution#")

## Q1 = lists all municipalities
q1=prepareQuery('''
  SELECT ?name WHERE {
    ?municipality a ?Class .
    ?municipality base:hasName ?name
  }
  ''',
  initNs = { "base": base}
)

r_municipalities=[]

for r in g.query(q1, initBindings = {'?Class': base.Municipality }):
  r_municipalities.append(r.name)

#converting to dataframe
rr_municipalities = pd.DataFrame (r_municipalities, columns = ['Municipality'])


# ----- UI
municipalities_selection= st.multiselect('Municipality',
    #municipalities,
    rr_municipalities,
    default=r_municipalities[16])

# displays additional information
st.subheader('About municipality')

#Linking Query 0: Find municipality
owl = Namespace("http://www.w3.org/2002/07/owl#")
q_wiki=prepareQuery('''
  SELECT ?wiki_municipality WHERE {
    ?municipality base:hasName ?municipality_name .
    ?municipality owl:sameAs ?wiki_municipality .
  }
  ''',
  initNs = {"base": base, "owl": owl}
)


wiki_link=[]
for c in municipalities_selection:
    for r in g.query(q_wiki, initBindings = {'municipality_name': Literal(c, datatype="http://www.w3.org/2001/XMLSchema#string")}):
        wiki_result=str(r.wiki_municipality)
        wiki_result=wiki_result.replace("https://wikidata.org/entity/","")
        
        wiki_link.append([c,r.wiki_municipality,wiki_result])


#Linking Query 1: Get the population of the municipality
endpoint_url = "https://query.wikidata.org/sparql"

query1 = """
SELECT ?population  
WHERE 
{
  ?wiki_municipality wdt:P1082 ?population . 
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". } # Helps get the label in your language, if not, then en language
}"""

# handles wiki queries
def get_results(endpoint_url, query, q_number):
    user_agent = "WDQS-example Python/%s.%s" % (sys.version_info[0], sys.version_info[1])
    # TODO adjust user agent; see https://w.wiki/CX6
    sparql = SPARQLWrapper(endpoint_url, agent=user_agent)
    query = query.replace("?wiki_municipality", "wd:"+q_number)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    return sparql.query().convert()


st.markdown('**Population **')
for c in wiki_link:
    results = get_results(endpoint_url, query1, c[2])

    for result in results["results"]["bindings"]:
        population=result.get("population").get("value")   
        st.caption(c[0]+' : '+population)

#Linking Query 2: Get the area of the municipality
query2 = """
SELECT ?area  
WHERE 
{
  ?wiki_municipality wdt:P2046 ?area . 
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". } # Helps get the label in your language, if not, then en language
}"""

st.markdown('**Area **')
for c in wiki_link:
    results = get_results(endpoint_url, query2, c[2])

    for result in results["results"]["bindings"]:
        area=result.get("area").get("value")   
        st.caption(c[0]+' : '+area)



# Q2 = lists stations for choosen municipalities
q2=prepareQuery('''
  SELECT ?station_name WHERE {
    ?municipality base:hasName ?municipality_name .
    ?location base:hasMunicipality ?municipality .
    ?station base:isLocatedIn ?location .
    ?station base:hasName ?station_name 
  }
  ''',
  initNs = {"base": base}
)

r_stations=[]

# for each item in selected municipality
for b in municipalities_selection :

    # select stations
    for r in g.query(q2, initBindings = {'municipality_name': Literal(b, datatype="http://www.w3.org/2001/XMLSchema#string")}):
        #st.write(r.station_name)
        r_stations.append(r.station_name)

#converting to dataframe
rr_stations = pd.DataFrame (r_stations, columns = ['Station'])


#UI component
station_selection=st.multiselect('Station',
    #stations,
    rr_stations,
    default=r_stations)

# Q4 = counts the amount of availible results with data 
q4=prepareQuery('''
  SELECT ?station (COUNT(?measurement) as ?count) WHERE {
     ?station base:hasName ?station_name .
     ?station base:hasMeasurement ?measurement .
  }
  ''',
  initNs = {"base": base}
)

sum_list=[]
for d in station_selection:
    for r in g.query(q4, initBindings = {'station_name': Literal(d, datatype="http://www.w3.org/2001/XMLSchema#string")}):
        sum_list.append(int(r[1]))
        #st.write(r[1])
total=sum(sum_list)
st.markdown(f'*Available Results: {total}*')



# Q4 = extracts coordinates for choosen stations
q4=prepareQuery('''
  SELECT ?longitud ?latitude ?station_name WHERE {
     ?station base:hasName ?station_name .
     ?station base:isLocatedIn ?location .
     ?location base:hasLatitude ?latitude .
     ?location base:hasLongitude ?longitud .
  }
  ''',
  initNs = {"base": base}
)

# constructs dataframe
df_coordinates= pd.DataFrame({'Latitude':[],'Longitude':[],'Station_Name':[]})

for a in station_selection:

    for r in g.query(q4, initBindings = {'station_name': Literal(a, datatype="http://www.w3.org/2001/XMLSchema#string")}):
        temporary=pd.DataFrame({'Latitude':[r.latitude],'Longitude':[r.longitud],'Station_Name':[r.station_name]})
        df_coordinates=df_coordinates.append(temporary, ignore_index = True)

# displays results as a table
#st.write(df_coordinates)

# UI MAP component 
my_map = folium.Map(
    location=[41.3874, 2.1686],
    zoom_start=9
)

#adds markers
for _, station in df_coordinates.iterrows():
    folium.Marker(
        location=[station['Latitude'],station['Longitude']],
        popup='<h4>'+station['Station_Name']+'</h4>'
        +'<br>Coordinates ['+station['Latitude']+station['Longitude']+']</br>',
        tooltip='<h4>'+station['Station_Name']+'</h4>',
        icon=folium.Icon(color='blue', prefix='fa', icon='circle') #station ['color']
    ).add_to(my_map)

# adds map
folium_static(my_map)


# Q6: lists all polutant availible for chosen stations
q6=prepareQuery('''
  SELECT DISTINCT ?pollutant_name WHERE {
     ?station base:hasName ?station_name .
     ?station base:hasMeasurement ?measurement .
     ?measurement base:hasPollutant ?pollutant_code .
     ?pollutant_code base:hasName ?pollutant_name .
  }
  ''',
  initNs = {"base": base}
)

# creates distinct list of availible polutants
polutant_availible=[]

for a in station_selection:
    for r in g.query(q6, initBindings = {'station_name': Literal(a, datatype="http://www.w3.org/2001/XMLSchema#string")}):
        if r.pollutant_name not in polutant_availible:
            polutant_availible.append(r.pollutant_name)


# UI component
polutant_selection= st.selectbox('Polutant to display', polutant_availible)


#  Q7 Lists available polutant for choosen polutant
q7=prepareQuery('''
  SELECT DISTINCT ?station_name  WHERE {
     ?pollutant base:hasName ?pollutant_name .
     ?station base:hasMeasurement ?measurement .
     ?measurement base:hasPollutant ?pollutant .
     ?station base:hasName ?station_name 
  }
  ''',
  initNs = {"base": base}
)

polutant_in_stations =[]
for r in g.query(q7, initBindings = {'pollutant_name': Literal(polutant_selection, datatype="http://www.w3.org/2001/XMLSchema#string")}):
    polutant_in_stations.append(r.station_name)

# UI component
polutant_station= st.selectbox('Station for polutant',
    polutant_in_stations)


# Q8: lists measures
q8=prepareQuery('''
  SELECT ?date ?value WHERE {
     ?station base:hasName ?station_name .
     ?station base:hasMeasurement ?measurement .
     ?measurement base:inDate ?date . 
     ?measurement base:hasValue ?value .
     ?measurement base:hasPollutant ?pollutant .
     ?pollutant base:hasName ?pollutant_name .
  }
  ''',
  initNs = {"base": base}
)


df1=pd.DataFrame({'Date':[],'Values':[]})
for r in g.query(q8, initBindings = {'station_name': Literal(polutant_station, datatype="http://www.w3.org/2001/XMLSchema#string"),
'pollutant_name': Literal(polutant_selection,datatype="http://www.w3.org/2001/XMLSchema#string")}):
    
    df2=pd.DataFrame({'Date':[r.date],'Values':[r.value]})
    df1=df1.append(df2, ignore_index = True)

# displays results as a table
#st.write(df1)


# UI plot bar chart component
bar_chart =px.bar(df1,
    x='Date',
    y='Values',
    #text='Units',
    color_discrete_sequence =['#F63366']*len(df1),
    template ='plotly_white')

st.plotly_chart(bar_chart) 



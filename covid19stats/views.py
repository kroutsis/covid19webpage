from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.generic import TemplateView
import folium
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import pylab as plt
import PIL, PIL.Image, io, base64
from io import BytesIO

labels = []
two_c_compartion = []
	
def home_page(request, *args, **kwargs):

    dfc, dfd, dfr = get_raw_data()

    date_columns, last_update_date, countries_with_patients_today, covid_results, array_info = manage_data(dfc, dfd, dfr)
    
    top_countries_with_patients_today = top_countries_with_cases(countries_with_patients_today)
    
    regions_with_most_patients_today = regions_with_most_patients(top_countries_with_patients_today, last_update_date)
    
    pie = situation_wordwide_pie(covid_results)
    
    m = worldmap(countries_with_patients_today)
	
    countries_regions = []
    for x, y in zip(countries_with_patients_today['Country/Region'], countries_with_patients_today['Province/State']):
        if type(y) is str and y != "":
            countries_regions.append(y +" | "+ x)
        else:
            countries_regions.append(str(x))
			
    countries_regions = sorted(countries_regions)

    info = [
        'First report of Covid-19: 12/31/19 - Wuhan China',
        'First dataset entry: ' + date_columns[0],
        'Last dataset Update: ' + date_columns[-1],
        'Total confirmed patients today: ' + comma_sep_num(int(covid_results[0])),
        'Total confirmed patients recovered: ' + comma_sep_num(int(covid_results[1])),
        'Total deaths from covid-19: ' + comma_sep_num(int(covid_results[2])),
        'New confirmed patients: ' + comma_sep_num(int(covid_results[3])),
        'Total people infected: ' + comma_sep_num(int(covid_results[0]) + int(covid_results[1]) + int(covid_results[2])),
        '(CFR)Covid-19 fatality rate: ' + str(round((int(covid_results[2]) * 100) / (int(covid_results[0]) + int(covid_results[1]) + int(covid_results[2])), 3)) + "%"
	]

    context = {
        'countries':countries_regions,
		'info':info,
        'pie':pie,
        'most_p_graph':regions_with_most_patients_today,
        'map':m._repr_html_(),
        'array_info': array_info.to_html(table_id='table_info')
        }
    
    if request.method == 'POST' and 'btnform1' in request.POST:
        get_output = str(request.POST.get('query'))
        c_info_result = country_info(dfc, dfd, dfr, date_columns, get_output)
        if get_output.find("|") != -1:
            t_get_output = get_output.split(" | ")
            if t_get_output[1] not in labels:
                labels.append(t_get_output[1])
        else:
            if get_output not in labels:
                labels.append(get_output)
        if get_output not in two_c_compartion:
            two_c_compartion.append(get_output)
        if len(two_c_compartion) > 1:
            c_to_c_compartion_result = country_to_country_compartion(dfc, date_columns, two_c_compartion)
            context.update({'c_to_c_compartion_output': c_to_c_compartion_result})
            if len(two_c_compartion) > 2:
                two_c_compartion.pop(0)
        if len(labels) > 6:
            labels.pop(0)
        c_compartion_info = covid_cases_compartion(dfc, dfr, dfd, last_update_date, labels)
        context.update({'c_info_output': c_info_result, 'c_compartion_output': c_compartion_info})

    return render(request, 'home.html', context)
    
def get_raw_data():
    
    raw_covid19_dataset_recovered = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_recovered_global.csv'
    raw_covid19_dataset_deaths = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_deaths_global.csv'
    raw_covid19_dataset_confirmed = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv'
    dfc = pd.read_csv(raw_covid19_dataset_confirmed)
    dfd = pd.read_csv(raw_covid19_dataset_deaths)
    dfr = pd.read_csv(raw_covid19_dataset_recovered)
    
    return dfc, dfd, dfr

def manage_data(dfc, dfd, dfr):
    
    date_columns = [col for col in dfc.columns if col not in ['Province/State', 'Country/Region', 'Lat', 'Long']]
    last_update_date = date_columns[-1]
    last_update_previous_date = date_columns[-2]
    countries_with_patients_today = dfc[['Province/State', 'Country/Region', 'Lat', 'Long', last_update_date, last_update_previous_date]][dfc[last_update_date] != 0].sort_values(by=[last_update_date], ascending=False)
    countries_with_patients_today_deaths = dfd[[last_update_date]][dfc[last_update_date] != 0].reindex(countries_with_patients_today.index)
    countries_with_patients_today_recoveries = dfr[[last_update_date]][dfc[last_update_date] != 0].reindex(countries_with_patients_today.index)
    countries_with_patients_today['Deaths'] = countries_with_patients_today_deaths.values
    x_name = last_update_date+"_x"
    y_name = last_update_date+"_y"
    countries_with_patients_today = countries_with_patients_today.merge(dfr[['Province/State', 'Country/Region', last_update_date]], on=('Province/State','Country/Region'), how='left').rename(columns={x_name:last_update_date,y_name:'Recoveries'})
    countries_with_patients_today['New Cases'] = countries_with_patients_today[last_update_date] - countries_with_patients_today[last_update_previous_date]
    countries_with_patients_today['Recoveries'] = countries_with_patients_today['Recoveries'].astype('Int64')
    countries_with_patients_today = countries_with_patients_today.fillna(0)
    countries_with_patients_today['Province/State'].replace({0:""}, inplace=True)
    countries_with_patients_today['CFR'] = round((countries_with_patients_today['Deaths'] * 100) / (countries_with_patients_today[last_update_date] + countries_with_patients_today['Deaths'] + countries_with_patients_today['Recoveries']), 2)
    countries_with_patients_today['CFR'] = countries_with_patients_today['CFR'].astype(str) + " %"

    array_info = countries_with_patients_today[['Province/State', 'Country/Region', last_update_date, 'New Cases', 'Recoveries', 'Deaths', 'CFR']]
    array_info = array_info.astype({'Recoveries' : int}) 
    array_info.rename(columns={last_update_date : 'Confirmed Patients'}, inplace=True)
    
    new_patients = int(countries_with_patients_today['New Cases'].sum())
    all_patients = int(dfc[[last_update_date]].sum())
    all_deaths = int(dfd[[last_update_date]].sum())
    all_recoveries = int(dfr[[last_update_date]].sum())
    covid_results = [all_patients, all_recoveries, all_deaths, new_patients]

    return date_columns, last_update_date, countries_with_patients_today, covid_results, array_info

def top_countries_with_cases(countries_with_patients_today):
    
    top_countries_with_patients_today = countries_with_patients_today.head(10)

    return top_countries_with_patients_today

def plot_to_image_format(plt):

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8').replace('\n', '')
    buffer.close()
    
    plt.close()
    
    return image_base64

def situation_wordwide_pie(covid_results):
    
    slices = covid_results[:-1]
    labels = ['Patients Today', 'Patients Recovered', 'Patients Died']
    colors = ['lightskyblue', 'yellow', 'red']
    plt.pie(slices, labels=labels, colors=colors, shadow=True, autopct='%1.1f%%', wedgeprops={'edgecolor':'black'})
    plt.title('Covid-19 Situation Wordwide')
    
    return plot_to_image_format(plt)

def covid_cases_compartion(dfc, dfr, dfd, last_update_date, labels):
    
    #labels = ['China', 'US', 'Italy', 'Iran', 'Spain']
    #labels.append(get_output)
    patients = []
    recoveries = []
    deaths = []
    
    for country in labels:
        patients.append(dfc[dfc['Country/Region'] == country][last_update_date].sum())
        recoveries.append(dfr[dfr['Country/Region'] == country][last_update_date].sum())
        deaths.append(dfd[dfd['Country/Region'] == country][last_update_date].sum())
    
    plt.style.use('ggplot')
    x = np.arange(len(labels))
    width = 0.25
    fig, ax = plt.subplots()
    
    rects1 = ax.bar(x , patients, width, label='Patients')
    rects2 = ax.bar(x + width, recoveries, width, label='Recoveries')
    rects3 = ax.bar(x - width, deaths, width, label='Deaths')

    offset_text = ax.get_yticks()
    ax.set_ylabel('Number of Patients' + set_label(offset_text[-1]))

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    #ax.set_yticklabels(np.arange(0, math.ceil(np.max(patients)), 1000))
    #plt.title('Covid-19 cases\n')
    
    def autolabel(rects):
        for rect in rects:
            h = rect.get_height()
            ax.text(rect.get_x()+rect.get_width()/2., 1.05*h, comma_sep_num(h), ha='center', va='bottom')
    
    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)
    
    plt.tight_layout()
    
    return plot_to_image_format(plt)

def regions_with_most_patients(top_countries_with_patients_today, last_update_date):
    
    countries_regions = []
    for x, y in zip(top_countries_with_patients_today['Country/Region'], top_countries_with_patients_today['Province/State']):
        if type(y) is str and x != y:
            countries_regions.append(y +" "+ x)
        else:
            countries_regions.append(x)
    
    def autolabel(num_of_patients):
        for i, v in enumerate(num_of_patients):
            ax.text(v , i , " "+comma_sep_num(v), va='center')
    
    #num_of_patients = list(top_countries_with_patients_today.iloc[:,-1])
    num_of_patients = list(top_countries_with_patients_today[last_update_date])

    plt.style.use('ggplot')
    plt.rcdefaults()
    fig, ax = plt.subplots()
    
    y_pos = np.arange(len(countries_regions)) #x axis
    
    bar = ax.barh(y_pos, num_of_patients, align='center')
    ax.set_title('Countries/Regions with most patients today')
    ax.set_yticklabels(countries_regions)
    
    offset_text = ax.get_xticks()
    ax.set_xlabel('Number of Patients' + set_label(offset_text[-1]))

    #ax.set_xticks(np.arange(0, max(num_of_patients), 3000000))
    ax.set_yticks(y_pos)
    
    autolabel(num_of_patients)
    
    plt.tight_layout()
    
    return plot_to_image_format(plt)

def country_info(dfc, dfd, dfr, date_columns, get_output):
    
    country_name = get_output
    if country_name.find("|") != -1:
        t_country_name = country_name.split(" | ")
        temp_country_data_c = dfc[dfc['Province/State'] == t_country_name[0]]
        num_of_patients_df = temp_country_data_c[date_columns]
        temp_country_data_d = dfd[dfd['Province/State'] == t_country_name[0]]
        num_of_deaths_df = temp_country_data_d[date_columns]
        temp_country_data_r = dfr[dfr['Province/State'] == t_country_name[0]]
        num_of_recoveries_df = temp_country_data_r[date_columns]
    else:
        temp_country_data_c = dfc[(dfc['Country/Region'] == country_name) & (pd.isna(dfc['Province/State']))]
        num_of_patients_df = temp_country_data_c[date_columns]
        temp_country_data_d = dfd[(dfd['Country/Region'] == country_name) & (pd.isna(dfd['Province/State']))]
        num_of_deaths_df = temp_country_data_d[date_columns]
        temp_country_data_r = dfr[(dfr['Country/Region'] == country_name) & (pd.isna(dfr['Province/State']))]
        num_of_recoveries_df = temp_country_data_r[date_columns]
    
    num_of_patients = []
    num_of_deaths = []
    num_of_recoveries = []
    dates_with_desease = []
    try:
        for i in date_columns:
            p_temp = int(num_of_patients_df[i])
            d_temp = int(num_of_deaths_df[i])
            r_temp = int(num_of_recoveries_df[i])
            if p_temp != 0:
                dates_with_desease.append(i)
                num_of_patients.append(p_temp)
                num_of_deaths.append(d_temp)
                num_of_recoveries.append(r_temp)
    except:
        print("Error Occured")
    #print(plt.style.available)
    plt.style.use('ggplot')
    plt.plot(dates_with_desease, num_of_patients, label='Current')
    plt.plot(dates_with_desease,num_of_recoveries, label='Recovered')
    plt.plot(dates_with_desease,num_of_deaths, label='Deceased')
    
    plt.title('Covid-19 '+ country_name +' cases')
    plt.xticks(dates_with_desease[1::12], rotation=50)

    offset_text = plt.gca().get_ylim()
    plt.ylabel('Number of Patients' + set_label(offset_text[1]))
    
    plt.legend()
    
    plt.tight_layout()
    
    return plot_to_image_format(plt)

def country_to_country_compartion(dfc, date_columns, two_c_compartion):
    
    country_name_1 = two_c_compartion[-1]
    country_name_2 = two_c_compartion[-2]
    
    if country_name_1.find("|") != -1:
        t_country_name = country_name_1.split(" | ")
        c1_data = dfc[dfc['Province/State'] == t_country_name[0]]
    else:
        c1_data = dfc[(dfc['Country/Region'] == country_name_1) & (pd.isna(dfc['Province/State']))]
    if country_name_2.find("|") != -1:
        t_country_name = country_name_2.split(" | ")
        c2_data = dfc[dfc['Province/State'] == t_country_name[0]]
    else:
        c2_data = dfc[(dfc['Country/Region'] == country_name_2) & (pd.isna(dfc['Province/State']))]
    #c1_data = dfc[dfc['Country/Region'] == country_name_1]
    #c2_data = dfc[dfc['Country/Region'] == country_name_2]
    
    num_of_patients_c1_df = c1_data[date_columns]
    num_of_patients_c2_df = c2_data[date_columns]
    
    num_of_patients_c1 = []
    num_of_patients_c2 = []
    dates_with_desease = []
    
    for i in date_columns:
        c1_temp = int(num_of_patients_c1_df[i])
        c2_temp = int(num_of_patients_c2_df[i])
        if c1_temp != 0 or c2_temp != 0:
            dates_with_desease.append(i)
            num_of_patients_c1.append(c1_temp)
            num_of_patients_c2.append(c2_temp)

    plt.style.use('ggplot')
    fig, (ax1, ax2, ax3) = plt.subplots(3)
    
    ax1 = plt.subplot(212)
    ax1.plot(dates_with_desease, num_of_patients_c2, label=country_name_2, color='blue')
    ax1.plot(dates_with_desease, num_of_patients_c1, label=country_name_1, color='red')
    plt.xticks(dates_with_desease[1::15], rotation=35)
    plt.title('Covid-19 cases compartion')
        
    ax2 = plt.subplot(221)
    ax2.plot(dates_with_desease, num_of_patients_c1, label=country_name_1, color='red')
    plt.xticks(dates_with_desease[1::30], rotation=45)
    plt.title(country_name_1)
    
    ax3 = plt.subplot(222)
    ax3.plot(dates_with_desease, num_of_patients_c2, label=country_name_2, color='blue')
    plt.xticks(dates_with_desease[1::30], rotation=45)
    plt.title(country_name_2)
    
    offset_text1 = ax1.get_yticks()
    if set_label(offset_text1[-1]) != "":
        ax1.set_ylabel('Number of Patients\n' + set_label(offset_text1[-1]))
    else:
        ax1.set_ylabel('Number of Patients')
    offset_text2 = ax2.get_yticks()
    if set_label(offset_text2[-1]) != "":
        ax2.set_ylabel('Number of Patients\n' + set_label(offset_text2[-1]))
    else:
        ax2.set_ylabel('Number of Patients')
    offset_text3 = ax3.get_yticks()
    if set_label(offset_text3[-1]) != "":
        ax3.set_ylabel(set_label(offset_text3[-1]))

    #mplcursors.cursor().connect("add", lambda sel: sel.annotation.set_text(num_of_patients_gr_df))
    plt.tight_layout()
    
    return plot_to_image_format(plt)

def worldmap(countries_with_patients_today):

    num_of_patients = list(countries_with_patients_today.iloc[:,-5])
    lat_long = list(zip(countries_with_patients_today.Lat, countries_with_patients_today.Long))
    m = folium.Map(location=[24.0000, 11.0000],zoom_start=2,tiles='cartodbpositron', max_bounds=True, max_zoom=4, min_zoom=2)
    for mappoint, patients in zip(lat_long, num_of_patients):
        i = lat_long.index(mappoint)
        if type(countries_with_patients_today.iloc[i]['Province/State']) is str:
            temp_prov_state = countries_with_patients_today.iloc[i]['Province/State']
        else:
            temp_prov_state = ""
        popup = "<b><u>"+ countries_with_patients_today.iloc[i]['Country/Region'] + " " + temp_prov_state + "</u></b><br>P:"+ str(num_of_patients[i]) +"(<font color='red'>&uarr;"+ str(countries_with_patients_today.iloc[i]['New Cases'])+ "</font>)<br>D:"+ str(countries_with_patients_today.iloc[i]['Deaths']) + "<br>R:"+ str(countries_with_patients_today.iloc[i]['Recoveries']).split('.')[0]
        if patients >= 6000000:
            circle = folium.Circle(mappoint, 400000, popup=popup, color='red', fill=True, fill_opacity=1)
        elif patients < 6000000 and patients >= 4000000:
            circle = folium.Circle(mappoint, 200000, popup=popup, color='red', fill=True, fill_opacity=1)
        elif patients < 4000000 and patients >= 2000000:
            circle = folium.Circle(mappoint, 100000, popup=popup, color='orangered', fill=True, fill_opacity=1)
        elif patients < 2000000 and patients >= 1000000:
            circle = folium.Circle(mappoint, 50000, popup=popup, color='tomato', fill=True, fill_opacity=1)
        elif patients < 1000000 and patients >= 500000:
            circle = folium.Circle(mappoint, 50000, popup=popup, color='darkorange', fill=True, fill_opacity=1)
        elif patients < 500000 and patients >= 100000:
            circle = folium.Circle(mappoint, 50000, popup=popup, color='orange', fill=True, fill_opacity=1)
        elif patients < 100000 and patients >= 50000:
            circle = folium.Circle(mappoint, 50000, popup=popup, color='gold', fill=True, fill_opacity=1)
        elif patients < 50000 and patients >= 5000:
            circle = folium.Circle(mappoint, 50000, popup=popup, color='yellow', fill=True, fill_opacity=1)
        elif patients < 5000:
            circle = folium.Circle(mappoint, 50000, popup=popup, color='lemonchiffon', fill=True, fill_opacity=1)
        circle.add_to(m)
    #m.get_root().html.add_child(folium.Element(legend))
    return m

def set_label(offset_text):

    label = ""
    if offset_text >= 1000000 and offset_text < 10000000:
        label = "(millions)"
    elif offset_text >= 10000000 and offset_text < 100000000:
        label = "(10 millions)"
    elif offset_text >= 100000000:
        label = "(100 millions)"

    return label

def comma_sep_num(number):

    return str(f"{number:,d}")


import sys
import os
from application import application
from flask import render_template, request, jsonify
from application.fitPhysics import fit_P2D
import pandas as pd
import numpy as np
import json
from application.ECfit import fitEC


@application.route('/', methods=['GET'])
def index():
    """ Impedance Analyzer Main Page """
    return render_template('index.html')


@application.route('/getExampleData', methods=['GET'])
def getExampleData():
    """ Gets the data from the selected example

    Parameters
    ----------
    filename : str
        filename for selecting example

    Returns
    -------
    data : jsonified data

    """

    filename = request.values["filename"]

    with open('./application/static/data/examples/' + filename, 'r') as f:
        contents = f.read()

    data = to_array(contents)

    return jsonify(data=data)


@application.route('/getUploadData', methods=['POST'])
def getUploadData():
    """ Gets uploaded data """
    f = request.files['data']
    contents = f.read()
    data = to_array(contents)

    return jsonify(data=data)


@application.route('/fitCircuit', methods=['POST'])
def fitCircuit():
    """ fits equivalent circuit

    Parameters
    ----------

    circuit : str
        string defining circuit to fit

    data : str
        string of data of comma separated values of freq, real, imag

    p0 : str
        comma deliminated string of initial parameter guesses

    Returns
    -------

    names : list of strings
        list of parameter names

    values : list of strings
        list of parameter values

    errors : list of strings
        list of parameter errors

    ecFit :


    Notes
    -----


    """
    data = request.values["data"].split(',')
    f = [float(f) for f in data[::3]]
    real = [float(r) for r in data[1::3]]
    imag = [float(i) for i in data[2::3]]
    data = list(zip(f, real, imag))

    circuit = request.values["circuit"]
    p0 = request.values["p0"]
    p0 = [float(p) for p in p0.split(',')]

    p_results, p_error, ecFit = fitEC.equivalent_circuit(data, circuit, p0)

    params = circuit.replace(',', '-').replace('/', '-').split('-')
    names = [param.replace('(', '').replace(')', '').replace('p', '') for param in params]

    return jsonify(names=names, values=p_results.tolist(), errors=p_error, ecFit=ecFit)


@application.route('/fitPhysics', methods=['POST'])
def fitPhysics():
    """ fits physics model

    """
    data = request.values["data"].split(',')
    f = [float(f) for f in data[::3]]
    real = [float(r) for r in data[1::3]]
    imag = [float(i) for i in data[2::3]]
    data = list(zip(f, real, imag))

    exp_data, p2dFit, sorted_results = fit_P2D(data)

    Z = pd.read_pickle('application/static/data/29000-Z.pkl')
    Z.index = range(len(Z))

    mask = [f for f, r, i in p2dFit]

    freq = [f for f, r, i in data]

    Z = Z.loc[sorted_results['run'].map(int).values, mask]
    p2d_simulations = pd.DataFrame(columns=['run', 'freq', 'real', 'imag'])

    p2d_simulations['real'] = Z.apply(lambda y: ','.join(y.map(lambda x: str(np.real(x))).values.tolist()), axis=1)
    p2d_simulations['imag'] = Z.apply(lambda y: ','.join(y.map(lambda x: str(np.imag(x))).values.tolist()), axis=1)
    p2d_simulations['freq'] = Z.apply(lambda y: ','.join(Z.columns.map(str)), axis=1)
    p2d_simulations['run'] = Z.index

    parameters = pd.read_csv('./application/static/data/model_runs-full.txt')
    P = parameters.loc[sorted_results['run'].map(int).values]

    to_skip = ['SOC_neg', 'SOC_pos', 'cs_max_neg', 'cs_max_pos',
                          'epsilon_sep', 'd2Udcp2_neg', 'd2Udcp2_pos',
                          'd3Udcp3_neg', 'd3Udcp3_pos']

    mask = [c for c in P.columns if c.split('[')[0] not in to_skip]
    P = P.loc[:, mask]

    p2d_simulations['param'] = P.apply(lambda y: str(sorted_results['scale'].loc[int(y['run'])]*1e4) + ',' + ','.join(y.map(lambda x: str(x)).values.tolist()), axis=1)

    p2d_simulations = p2d_simulations.values.tolist()

    p2d_names = ['fit parameter[cm^2]'] + (P.columns.values.tolist())

    best_fit = sorted_results['run'].iloc[0]
    param_Series = parameters.loc[best_fit]

    p2d_residuals = sorted_results.values.tolist()

    parameters = []
    parameters.append({"name": "fit parameter", "units": "cm^2",
                       "value": sorted_results['scale'].iloc[0]*1e4,
                       "sensitivity": "x"})

    for i, parameter in enumerate(param_Series.index):
        if parameter.split('[')[0] not in parameters_to_skip:
            parameters.append({"name": parameter.split('[')[0],
                               "units": parameter.split('[')[-1].strip("]"),
                               "value": param_Series.iloc[i],
                               "sensitivity": "x"})

    names = [x['name'] for x in parameters]
    units = [x['units'] for x in parameters]
    values = [x['value'] for x in parameters]
    errors = ['NaN' for x in parameters]

    return jsonify(pbFit=p2dFit, names=names, units=units,
                   values=values, errors=errors, results=p2d_residuals,
                   simulations=p2d_simulations, exp_data=exp_data)


def to_array(input):
    """ parse strings of data from ajax requests to return

    """

    try:
        input = input.decode("utf-8")
    except AttributeError:
        pass

    input = input.replace('\r\n', ',')
    input = input.replace('\n', ',')
    col0 = [float(x) for x in input.split(',')[0:-1:3]]
    col1 = [float(x) for x in input.split(',')[1:-1:3]]
    col2 = [float(x) for x in input.split(',')[2:-1:3]]

    return list(zip(col0, col1, col2))

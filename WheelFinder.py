from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)

HOME_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Home</title>
    <style>
      body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f7fa; margin: 0; }
      .container { background: #fff; max-width: 480px; margin: 4em auto; padding: 2.5em; border-radius: 16px;
                   box-shadow: 0 4px 32px rgba(0, 0, 0, 0.08); text-align: center; }
      h1 { color: #00669b; margin-bottom: 1.1em; }
      .profile-btn { background: #00669b; color: #fff; border: none; border-radius: 6px; font-size: 1.09em; 
                     padding: 0.8em 1.8em; cursor: pointer; margin-top: 15px;
                     box-shadow: 0 2px 4px rgba(140,180,214,0.05); transition: background 0.2s; }
      .profile-btn:hover { background: #0098db; }
    </style>
</head>
<body>
  <div class="container">
    <h1>Welcome</h1>
    <p>Click below to create your user profile.</p>
    <form action="{{ url_for('profile') }}">
      <button class="profile-btn" type="submit">Create Profile</button>
    </form>
  </div>
</body>
</html>
'''

PROFILE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>User Profile</title>
    <style>
      body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f7fa; margin: 0; }
      .container { background: #fff; max-width: 500px; margin: 3em auto; padding: 2.5em;
                   border-radius: 16px; box-shadow: 0 4px 32px rgba(0, 0, 0, 0.08);}
      h2 { color: #00669b; margin-bottom: 1.1em; }
      .form-row { margin-bottom: 1.1em; }
      label { display: block; margin-bottom: 0.3em; font-weight: 500;}
      input, select {
        width: 100%; font-size: 1.03em; padding: 0.6em 0.5em; margin-top: 0.1em;
        border: 1px solid #a3bcd6; border-radius: 4px; background: #f7fafc;
      }
      button {
        background: #00669b; color: #fff; border: none; border-radius: 6px;
        font-size: 1.07em; padding: 0.8em 2em; cursor: pointer;
        margin-top: 12px; box-shadow: 0 2px 4px rgba(140,180,214,0.08);
        transition: background 0.2s;
      }
      button:hover { background: #0098db; }
      .result { margin-top: 2em; background: #e8f7fd; border-radius: 8px; padding: 1.1em; }
      .next-btn { background: #0098db; color: #fff; border: none; border-radius: 6px; padding: 0.7em 2em;
                 font-size: 1.04em; margin-top: 1em; cursor: pointer;}
      .next-btn:hover { background: #42b1f5; }
    </style>
</head>
<body>
  <div class="container">
    <h2>Create Your Profile</h2>
    <form method="post">
      <div class="form-row">
        <label for="age">Age</label>
        <input id="age" name="age" type="number" min="0" max="120" required>
      </div>
      <div class="form-row">
        <label for="commuter">Commuter Miles per Week</label>
        <input id="commuter" name="commuter" type="number" min="0" step="1" placeholder="Miles driven per week" required>
      </div>
      <div class="form-row">
        <label for="gender">Gender</label>
        <select id="gender" name="gender" required>
          <option value="">Select...</option>
          <option>Female</option>
          <option>Male</option>
          <option>Non-binary</option>
          <option>Prefer not to say</option>
        </select>
      </div>
      <div class="form-row">
        <label for="income">Income</label>
        <input id="income" name="income" type="number" min="0" step="1000" placeholder="USD" required>
      </div>
      <button type="submit">Submit</button>
    </form>
    {% if result %}
      <div class="result">
        <h4>Your Profile:</h4>
        <ul>
          <li>Age: {{ result['age'] }}</li>
          <li>Miles per week: {{ result['commuter'] }}</li>
          <li>Gender: {{ result['gender'] }}</li>
          <li>Income: ${{ result['income'] }}</li>
        </ul>
        <form action="{{ url_for('preferences') }}">
          <button class="next-btn" type="submit">Set Preferences</button>
        </form>
      </div>
    {% endif %}
  </div>
</body>
</html>
'''

PREFERENCES_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Preferences</title>
    <style>
      body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f7fa; margin: 0; }
      .container {
        background: #fff;
        max-width: 800px;
        margin: 3em auto;
        padding: 2em 2.5em 2em 2.5em;
        border-radius: 16px;
        box-shadow: 0 4px 32px rgba(0, 0, 0, 0.08);
      }
      h2 {
        margin-bottom: 1.5em;
        color: #00669b;
        text-align: center;
      }
      .radio-row {
        display: flex;
        align-items: center;
        margin-bottom: 1.5em;
        font-size: 1.1em;
      }
      .pref-label {
        min-width: 150px;
        font-weight: 500;
        margin-right: 14px;
      }
      .radio-label {
        position: relative;
        margin-right: 14px;
        margin-left: 2px;
        cursor: pointer;
        padding-left: 24px;
        user-select: none;
        transition: color 0.2s;
      }
      .radio-label input[type="radio"] {
        opacity: 0;
        position: absolute;
        left: 0;
        top: 2px;
      }
      .custom-radio {
        position: absolute;
        left: 0;
        top: 2px;
        height: 18px;
        width: 18px;
        background-color: #f7fafc;
        border: 2px solid #a3bcd6;
        border-radius: 50%;
        transition: border 0.2s;
      }
      .radio-label input[type="radio"]:checked ~ .custom-radio {
        background-color: #1e90ff;
        border-color: #1e90ff;
      }
      .custom-radio:after {
        content: "";
        position: absolute;
        display: none;
      }
      .radio-label input[type="radio"]:checked ~ .custom-radio:after {
        display: block;
      }
      .radio-label .custom-radio:after {
        top: 4px;
        left: 4px;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: white;
        position: absolute;
      }
      button {
        background: #00669b;
        color: #fff;
        padding: 0.7em 2em;
        border: none;
        border-radius: 6px;
        font-size: 1.04em;
        cursor: pointer;
        box-shadow: 0 2px 4px rgba(140,180,214,0.1);
        margin-top: 12px;
        transition: background 0.2s;
      }
      button:hover {
        background: #0098db;
      }
      ul {
        margin-top: 1.5em;
        padding-left: 1.8em;
      }
    </style>
</head>
<body>
    <div class="container">
    <h2>Set Weights for Your Preferences</h2>
    <form method="post">
      {% for pref, name in preferences %}
        <div class="radio-row">
          <div class="pref-label">{{ pref }}:</div>
          <label class="radio-label">
            <input type="radio" name="{{ name }}" value="0" required>
            <span class="custom-radio"></span> No Preference
          </label>
          {% for w in range(1, 11) %}
            <label class="radio-label">
              <input type="radio" name="{{ name }}" value="{{ w }}">
              <span class="custom-radio"></span> {{ w }}
            </label>
          {% endfor %}
        </div>
      {% endfor %}
      <button type="submit">Submit</button>
    </form>
    {% if result %}
      <div>
        <h3>Result</h3>
        <ul>
        {% for pref, val in result.items() %}
          <li>{{ pref }}: {% if val == '0' %}No Preference{% else %}{{ val }}{% endif %}</li>
        {% endfor %}
        </ul>
      </div>
    {% endif %}
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HOME_HTML)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    result = None
    if request.method == 'POST':
        result = {
            'age': request.form['age'],
            'commuter': request.form['commuter'],
            'gender': request.form['gender'],
            'income': request.form['income']
        }
    return render_template_string(PROFILE_HTML, result=result)

@app.route('/preferences', methods=['GET', 'POST'])
def preferences():
    pref_names = [
        ("Fuel Efficiency", "weight_fuel"),
        ("Size", "weight_size"),
        ("Drive", "weight_drive"),
        ("Transmission", "weight_transmission"),
    ]
    result = None
    if request.method == 'POST':
        result = {}
        for pref, name in pref_names:
            val = request.form.get(name, '0')
            result[pref] = val
    return render_template_string(PREFERENCES_HTML, preferences=pref_names, result=result)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)


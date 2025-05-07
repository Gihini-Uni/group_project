This github repository contains a flask based web application which the user can track income and expenses. 

After downloading the folder, the below steps must be followed to run the application

1.⁠ ⁠Create a virtual environment by using the following command in command prompt inside the
project folder.
	⁠py -3 -m venv .venv

2.⁠ ⁠Activate the corresponding environment:
	⁠.venv\Scripts\activate

3.⁠ ⁠Within the activated environment, use the following command to install Flask:
	⁠pip install -r requirements.txt

4.⁠ ⁠Run the app
	⁠flask run --debug

Recommendation by the lecturer during the Viva: Display the list of existing Income & Expense categories on the Settings page.
To do this, simply change the code line, 
*<div class="me-5" style="display: none;">* to *<div class="me-5" style="display: grid;">*
	in settings.html (templates/settings.html) at lines 182 and 209.

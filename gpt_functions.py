"""DO NOT RUN"""

import os
import openai
import tiktoken
import pandas as pd
import re

class GPTFunctions:
    def __init__(self):
        if not os.path.exists('violationsWithFixedContent.csv'):
            with open('violationsWithFixedContent.csv', 'w') as file:
                file.write('id,impact,tags,description,help,helpUrl,nodeImpact,nodeHtml,nodeTarget,nodeType,message,numViolation\n')
        self.df = pd.read_csv('violationsWithFixedContent.csv')


    # function to get responses given system and user messages
    def GPT_response(self, system, user):
        # print("\n...................................... new call ...............................................")
        # print(user)
        response = openai.chat.completions.create(
            model='gpt-3.5-turbo-16k',
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user}
            ]
        )
        # print("...................................... response...............................................")
        # print(response.choices[0].message.content)
        return response.choices[0].message.content
    


    """BASELINE ReAct Prompt"""

    # function returns system message and user message for a given row index of the dataframe - no more DOM
    def generate_prompt(self, row_index):
        system_msg = """You are an assistant who will correct web accessibility issues of a provided website.
                I will provide you with an incorrect line of HTML. Provide a correction.
                Here are a few examples:

                E.g.
                Incorrect: [['<h3></h3>', '<h3></h3>']]
                Issue: There must be some form of text between heading tags. 
                Correct: [['<h3>Some heading text</h3>', '<h3>Some heading text</h3>']]
                
                Incorrect: [['<img src="image.png">', '<img src="image.png">']]
                Issue: The images lack an alt description. 
                Correct: [['<img src="image.png" alt="Description">', '<img src="image.png" alt="Description">']]
                
                Incorrect: [['<a href=""></a>', '<a href=""></a>']]
                Correct: [['<a href="url">Link text</a>', '<a href="url">Link text</a>']]

                Incorrect: [['<div id="accessibilityHome">\n<a aria-label="Accessibility overview" href="https://explore.zoom.us/en/accessibility">Accessibility Overview</a>\n</div>']]
                Issue: The links are empty and have no URL or text description. 
                Correct: [['<div id="accessibilityHome" role="navigation">\n<a aria-label="Accessibility overview" href="https://explore.zoom.us/en/accessibility">Accessibility Overview</a>\n</div>']]"""


        user_msg = f"""

        Error: {self.df['id'][row_index]}
        Description: {self.df['description'][row_index]}
        Suggested change: {self.df['help'][row_index]}

        Incorrect: {self.df['nodeHtml'][row_index]}"""
        return system_msg, user_msg


    """Function for getting GPT corrections"""

    # function returns the corrected part of GPT response
    def get_correction(self, row_index):
        # obtain response from GPT by calling prompt generation and chat functions
        system_msg = self.generate_prompt(row_index)[0]
        user_msg = self.generate_prompt(row_index)[1]
        response = self.GPT_response(system_msg, user_msg)

        # extract the "correct" part using regex
        correct_headers = re.search(r"Correct:\s*(\[\[.*\]\])", response)
        if correct_headers:
            return correct_headers.group(1)
        # means no corrections needed
        else:
            return self.df['nodeHtml'][row_index]

gpt_functions = GPTFunctions()
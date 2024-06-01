
import os
import requests
import openai
import tiktoken
from typing import List
import re
import asyncio

from models.task import ExecuteThreadTask

from classes.ConfigManagerClass import ConfigManager

from my_modules.my_logging import create_logger

# NOTE: Already included in GPTAssistantManager as a module level function
def prompt_text_replacement(logger, gpt_prompt_text, replacements_dict=None):
    if replacements_dict:
        prompt_text_replaced = gpt_prompt_text.format(**replacements_dict)   
    else:
        prompt_text_replaced = gpt_prompt_text

    logger.debug(f"replacements_dict: {replacements_dict}")
    logger.debug(f"prompt_text_replaced: {prompt_text_replaced[0:75]}")
    return prompt_text_replaced

class GPTChatCompletion:
    def __init__(self, gpt_client=None, yaml_data=None):
        self.config = yaml_data
        self.gpt_client = gpt_client

        #LOGGING
        stream_logs = True
        runtime_logger_level = 'INFO'

        self.logger = create_logger(
            dirname='log',
            logger_name='GPTChatCompletionClass',
            debug_level=runtime_logger_level,
            mode='w',
            stream_logs=stream_logs
            )

    async def make_singleprompt_gpt_response(
            self,
            prompt_text, 
            replacements_dict=None,
            gpt_model=None
            ) -> str:
        """
        Asynchronously generates a GPT response for a single prompt.

        This method takes a single prompt, optionally applies replacements, and generates a response using the GPT model. It also handles sending the response and optionally playing the corresponding voice message.

        Parameters:
        - prompt_text (str): The text prompt to generate a response for.
        - replacements_dict (dict, optional): A dictionary of replacements to apply to the prompt text.
        - incl_voice (str): Specifies whether to include voice output ('yes' or 'no'). Default is 'yes'.
        - voice_name (str): The name of the voice to be used in the text-to-speech service. Default is 'nova'.

        Returns:
        - str: The generated GPT response.

        """
        self.logger.info(f"Entered 'make_singleprompt_gpt_response'")
        self.logger.info(f"prompt_text: {prompt_text}")
        self.logger.info(f"replacements_dict: {replacements_dict}")
        self.logger.info(f"gpt_model: {gpt_model}")
        
        try:
            prompt_text = prompt_text_replacement(
                logger = self.logger,
                gpt_prompt_text=prompt_text,
                replacements_dict = replacements_dict
                )
            
            prompt_listdict = self._make_string_gptlistdict(
                prompt_text=prompt_text,
                prompt_text_role='user'
                )
            try:
                gpt_response = self._openai_gpt_chatcompletion(
                    messages_dict_gpt=prompt_listdict,
                    gpt_model=gpt_model
                    )
            except Exception as e:
                self.logger.error(f"Error occurred in '_openai_gpt_chatcompletion': {e}")        
        except Exception as e:
            self.logger.error(f"Error occurred in 'make_singleprompt_gpt_response': {e}")

        self.logger.info(f"prompt_text: {prompt_text}")
        self.logger.info(f"final gpt_response: {gpt_response}")
        return gpt_response
    
    def _openai_gpt_chatcompletion(
            self,
            messages_dict_gpt:list[dict],
            max_characters=300,
            max_attempts=3,
            frequency_penalty=1,
            presence_penalty=1,
            temperature=0.6,
            gpt_model=None
            ) -> str: 
        """
        Sends a list of messages to the OpenAI GPT self.config.gpt_model and retrieves a generated response.

        This function interacts with the OpenAI GPT self.config.gpt_model to generate responses based on the provided message structure. It attempts to ensure the response is within a specified character limit, retrying up to a maximum number of attempts if necessary.

        Parameters:
        - messages_dict_gpt (list[dict]): A list of dictionaries, each representing a message in the conversation history, formatted for the GPT prompt.
        - max_characters (int): Maximum allowed character count for the generated response. Default is 200 characters.
        - max_attempts (int): Maximum number of attempts to generate a response within the character limit. Default is 5 attempts.
        - frequency_penalty (float): The frequency penalty parameter to control repetition in the response. Default is 1.
        - presence_penalty (float): The presence penalty parameter influencing the introduction of new concepts in the response. Default is 1.
        - temperature (float): Controls randomness in the response generation. Lower values make responses more deterministic. Default is 0.6.

        Returns:
        - str: The content of the message generated by the GPT self.config.gpt_model. If the maximum number of attempts is exceeded without generating a response within the character limit, an exception is raised.

        Raises:
        - ValueError: If the initial message exceeds a token limit after multiple attempts to reduce its size.
        - Exception: If the maximum number of retries is exceeded without generating a valid response.
        """
        def _count_tokens(text:str) -> int:
            try:
                encoding = tiktoken.encoding_for_model(model_name=self.config.gpt_model)
                tokens_in_text = len(encoding.encode(text))
            except:
                raise ValueError("tiktoken.encoding_for_model() failed")

            return tokens_in_text

        def _count_tokens_in_messages(messages: List[dict]) -> int:
            try:
                total_tokens = 0
                for message in messages:
                    # Using .get() with default value as an empty string
                    role = message.get('role', '')
                    content = message.get('content', '')

                    # Count tokens in role and content
                    total_tokens += _count_tokens(role) + _count_tokens(content)
                self.logger.debug(f"Total Tokens: {total_tokens}")
                return total_tokens
            except:
                raise ValueError("_count_tokens_in_messages() failed")

        def _strip_prefix(text):
            # Regular expression pattern to match the prefix <<<[some_name]>>>:
            # Use re.sub() to replace the matched pattern with an empty string
            pattern = r'<<<[^>]*>>>'
            stripped_text = re.sub(pattern, '', text)

            #finally, strip out any extra colons that typically tend to prefix the message.
            #Sometimes it can be ":", ": :", " : ", etc. Only strip if it's the first characters (excluding spaces) 
            stripped_text = stripped_text.lstrip(':').lstrip(' ').lstrip(':').lstrip(' ') 

            return stripped_text

        self.logger.debug("This is the messages_dict_gpt submitted to GPT ChatCompletion")
        self.logger.debug(f"The number of tokens included at start is: {_count_tokens_in_messages(messages=messages_dict_gpt)}")
        self.logger.debug(messages_dict_gpt)

        gpt_model = gpt_model or self.config.gpt_model
        counter=0
        try:
            while _count_tokens_in_messages(messages=messages_dict_gpt) > 2000:
                if counter > 10:
                    error_message = f"Error: Too many tokens {token_count} even after 10 attempts to reduce count"
                    self.logger.error(error_message)
                    raise ValueError(error_message)
                self.logger.debug("Entered _count_tokens_in_messages() > ____")
                token_count = _count_tokens_in_messages(messages=messages_dict_gpt)
                self.logger.warning(f"The messages_dict_gpt contained too many tokens {(token_count)}, .pop(0) first dict")
                messages_dict_gpt.pop(0)
                counter+=1
        except Exception as e:
            self.logger.error(f"Exception ocurred in _openai_gpt_chatcompletion() during _count_tokens_in_messages(): {e}")
        
        self.logger.debug(f"messages_dict_gpt submitted to GPT ChatCompletion (tokens: {_count_tokens_in_messages(messages=messages_dict_gpt)})")
        self.logger.debug(messages_dict_gpt)

        #Call to OpenAI #TODO: This loop is wonky.  Should probably divert to a 'while' statement
        for attempt in range(max_attempts):
            self.logger.debug(f"THIS IS ATTEMPT #{attempt + 1}")
            try:
                generated_response = self.gpt_client.chat.completions.create(
                    model=self.config.gpt_model,
                    messages=messages_dict_gpt,
                    presence_penalty=presence_penalty,
                    frequency_penalty=frequency_penalty,
                    temperature=temperature
                )
            except Exception as e:
                self.logger.error(f"Exception occurred during API call: {e}: Attempt {attempt + 1} of {max_attempts} failed.")
                continue

            self.logger.debug(f"Completed generated response using self.gpt_client.chat.completions.create")          
            gpt_response_text = generated_response.choices[0].message.content
            gpt_response_text_len = len(gpt_response_text)
    
            self.logger.debug(f"generated_response type: {type(generated_response)}, length: {gpt_response_text_len}:")

            if gpt_response_text_len < max_characters:
                self.logger.debug(f'OK: The generated message was <{max_characters} characters')
                self.logger.debug(f"gpt_response_text: {gpt_response_text}")
                break
            else: # Did not get a msg < n chars, try again.
                self.logger.warning(f'gpt_response_text_len: >{max_characters} characters, retrying call to _openai_gpt_chatcompletion')
                messages_dict_gpt_updated = [{'role':'user', 'content':f"{self.config.shorten_response_length_prompt}: '{gpt_response_text}'"}]
                generated_response = self.gpt_client.chat.completions.create(
                    model=self.config.gpt_model,
                    messages=messages_dict_gpt_updated,
                    presence_penalty=presence_penalty,
                    frequency_penalty=frequency_penalty,
                    temperature=temperature
                    )
                gpt_response_text = generated_response.choices[0].message.content
                gpt_response_text_len = len(gpt_response_text)

                if gpt_response_text_len > max_characters:
                    self.logger.warning(f'gpt_response_text length was {gpt_response_text_len} characters (max: {max_characters}), trying again...')
                elif gpt_response_text_len < max_characters:
                    self.logger.debug(f"OK on attempt --{attempt}-- gpt_response_text: {gpt_response_text}")
                    break
        else:
            message = "Maxium GPT call retries exceeded"
            self.logger.error(message)        
            raise Exception(message)

        # Strip the prefix from the response
        gpt_response_text = _strip_prefix(gpt_response_text)
        
        return gpt_response_text

    def _make_string_gptlistdict(
            self,
            prompt_text, 
            prompt_text_role='user'
            ) -> list[dict]:
        """
        Returns:
        - list[dict]: A list containing a single dictionary with the message text and role.
        """
        prompt_listdict = [{'role': prompt_text_role, 'content': f'{prompt_text}'}]
        return prompt_listdict
    
    def get_models(self):
        """
        Function to fetch the available models from the OpenAI API.

        Args:
            api_key (str): The API key for the OpenAI API.

        Returns:
            dict: The JSON response from the API containing the available models.
        """
        url = 'https://api.openai.com/v1/models'
        headers = {'Authorization': f'Bearer {self.config.openai_api_key}'}
        response = requests.get(url, headers=headers)

        return response.json()

if __name__ == '__main__':
    import time
    ConfigManager.initialize(yaml_filepath=r'C:\_repos\chatzilla_ai\config\config.yaml')
    config = ConfigManager.get_instance()

    gpt_client = openai.OpenAI(api_key = config.openai_api_key)
    gpt_chat_completion = GPTChatCompletion(gpt_client=gpt_client, yaml_data=config)

    # # test2 -- Get models
    # gpt_models = get_models(
    #     api_key=config.openai_api_key
    #     )
    # print("GPT Models:")
    # print(json.dumps(gpt_models, indent=4))

    # # test3 -- call to chatgpt chatcompletion
    # gpt_chat_completion._openai_gpt_chatcompletion(
    #     messages_dict_gpt=[
    #         {'role':'user', 'content':'Whats a tall buildings name?'}, 
    #         {'role':'user', 'content':'Whats a tall Statues name?'}
    #         ],
    #     max_characters=config.assistant_response_max_length,
    #     max_attempts=5,
    #     frequency_penalty=1,
    #     presence_penalty=1,
    #     temperature=0.7
    #     )

    # # Test4 -- call to make_singleprompt_gpt_response
    # Note, cannot use 'await' in a synchronous function because it's not an async function
    # Measure time to complete
    start = time.time()
    response = asyncio.run(gpt_chat_completion.make_singleprompt_gpt_response(
        prompt_text=r"What is the tallest building in {country}?",
        replacements_dict={'country':'Dubai'},
        gpt_model=config.gpt_model
        ))
    end = time.time()
    print(f"Time to complete: {end - start}")
    print(f"This is the GPT Response: {response}")


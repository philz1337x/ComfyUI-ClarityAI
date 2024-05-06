import requests
from requests.models import PreparedRequest
from PIL import Image
import numpy as np
import torch
from torchvision.transforms import ToPILImage
from io import BytesIO
import os
import time

API_KEY = os.environ.get("CAI_API_KEY")

# Check for API key in file as a backup, not recommended
try:
    if not API_KEY:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(dir_path, "cai_platform_key.txt"), "r") as f:
            API_KEY = f.read().strip()
        # Validate the key is not empty
        if API_KEY.strip() == "":
            raise Exception(f"API Key is required to use Clarity AI. \nPlease set the CAI_API_KEY environment variable to your API key or place in {dir_path}/cai_platform_key.txt.")
        
except Exception as e:
    print(f"\n\n***API Key is required to use Clarity AI. Please set the CAI_API_KEY environment variable to your API key or place in {dir_path}/cai_platform_key.txt.***\n\n")

#ROOT_API = "https://api.clarityai.cc/v1/upscale"
ROOT_API = "https://v1-upscale-endpoint-oak26mtdga-ey.a.run.app"


class ClarityBase:
    API_ENDPOINT = ""
    POLL_ENDPOINT = ""
    ACCEPT = ""

    @classmethod
    def INPUT_TYPES(cls):
        return cls.INPUT_SPEC

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "call"
    CATEGORY = "Clarity AI"

    def call(self, *args, **kwargs):
        
        buffered = BytesIO()
        files = {'none': None}
        data = None
        
        image = kwargs.get('image', None)
        if image is not None:
            kwargs["mode"] = "image-to-image"
            kwargs.pop("aspect_ratio", None)
            image = ToPILImage()(image.squeeze(0).permute(2,0,1))
            image.save(buffered, format="PNG")
            files = self._get_files(buffered, **kwargs)
        else:
            kwargs.pop("strength", None)

        style = kwargs.get('style', False)
        if style is False:
            kwargs.pop('style_preset', None)

        kwargs['comfyui'] = True

        headers = {
            "Authorization": API_KEY,
        }

        if kwargs.get("api_key_override"):
            headers = {
                "Authorization": kwargs.get("api_key_override"),
            }

        if headers.get("Authorization") is None:
            raise Exception(f"No Clarity AI key set.\n\nUse your Clarity AI API key by:\n1. Setting the CAI_API_KEY environment variable to your API key\n3. Placing inside cai_platform_key.txt\n4. Passing the API key as an argument to the function with the key 'api_key_override'")

        headers["Accept"] = self.ACCEPT

        data = self._get_data(**kwargs)

        req = PreparedRequest()
        req.prepare_method('POST')
        req.prepare_url(f"{ROOT_API}{self.API_ENDPOINT}", None)
        req.prepare_headers(headers)
        req.prepare_body(data=data, files=files)
        response = requests.Session().send(req)

        if response.status_code == 200:
            if self.POLL_ENDPOINT != "":
                id = response.json().get("id")
                timeout = 550
                start_time = time.time()
                while True:
                    response = requests.get(f"{ROOT_API}{self.POLL_ENDPOINT}{id}", headers=headers, timeout=timeout)
                    if response.status_code == 200:
                        print("took time: ", time.time() - start_time)
                        if self.ACCEPT == "image/*":
                            return self._return_image(response)
                        if self.ACCEPT == "video/*":
                            return self._return_video(response)
                        break
                    elif response.status_code == 202:
                        time.sleep(10)
                    elif time.time() - start_time > timeout:
                        raise Exception("Clarity AI API Timeout: Request took too long to complete")
                    else:
                        error_info = response.json()
                        raise Exception(f"Clarity AI API Error: {error_info}")
            else:
                result_image = Image.open(BytesIO(response.content))
                result_image = result_image.convert("RGBA")
                result_image = np.array(result_image).astype(np.float32) / 255.0
                result_image = torch.from_numpy(result_image)[None,]
                return (result_image,)
        else:
            print("Fehler!! Status Code:", response.status_code)
            error_info = response.text
            print("error_info: " + error_info)
            if response.status_code == 401:
                raise Exception("Clarity AI API Error: Unauthorized.\n\nUse your Clarity AI API key by:\n1. Setting the CAI_API_KEY environment variable to your API key\n3. Placing inside cai_platform_key.txt\n4. Passing the API key as an argument to the function with the key 'api_key_override' \n\n \n\n")
            if response.status_code == 402:
                raise Exception("Clarity AI API Error: Not enough credits.\n\nPlease ensure your Clarity AI API account has enough credits to complete this action. \n\n \n\n")
            if response.status_code == 400:
                raise Exception(f"Clarity AI API Error: Bad request.\n\n{error_info} \n\n \n\n")
            else:
                raise Exception(f"Clarity AI API Error: {error_info}")
    
    def _return_image(self, response):
        result_image = Image.open(BytesIO(response.content))
        result_image = result_image.convert("RGBA")
        result_image = np.array(result_image).astype(np.float32) / 255.0
        result_image = torch.from_numpy(result_image)[None,]
        return (result_image,)

    def _return_video(self, response):
        result_video = response.content
        return (result_video,)

    def _get_files(self, buffered, **kwargs):
        return {
            "image": buffered.getvalue()
        }

    def _get_data(self, **kwargs):
        return {k: v for k, v in kwargs.items() if k != "image"}


class ClarityAIUpscaler(ClarityBase):
    API_ENDPOINT = ""
    POLL_ENDPOINT  = ""
    ACCEPT = "image/*"
    INPUT_SPEC = {
        "required": {
            "image": ("IMAGE",),
        },
        "optional": {
            "prompt": ("STRING", {"multiline": True}),
            "creativity": ("FLOAT", {"default": 0, "min": -10, "max": 10, "step": 1}),
            "resemblance": ("FLOAT", {"default": 0, "min": -10, "max": 10, "step": 1}),
            "dynamic": ("FLOAT", {"default": 0, "min": -10, "max": 10, "step": 1}),
            "fractality": ("FLOAT", {"default": 0, "min": -10, "max": 10, "step": 1}),
            "style": (["default", "portrait", "anime"],),
            "scale_factor": (["2", "4", "6", "8", "10", "12", "14", "16"],),
            "api_key_override": ("STRING", {"multiline": False}),
        }
    }

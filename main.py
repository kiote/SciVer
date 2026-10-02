from tqdm import tqdm
import json
import argparse
import os
import sys
from utils.constant import COT_PROMPT, DEFAULT_MODEL
try:
    from transformers.utils import logging
    logging.set_verbosity_error()
except ImportError:
    logging = None

def main(
    model_name: str, 
    prompt: str, 
    queries: list, 
    output_path: str, 
    n: int=1,
    thinking: str=None)-> None:
    pi_options = {}
    if model_name.startswith("pi/"):
        from model_inference.pi_rpc import generate_response
        pi_options["thinking"] = thinking
    elif thinking is not None:
        raise ValueError("--thinking applies only to pi/ models")
    elif model_name.startswith("ollama/"):
        from model_inference.ollama_chat import generate_response
    elif model_name == "laya" or model_name.startswith("laya/"):
        from model_inference.laya_text import generate_response
    elif "gpt" in model_name:
        from model_inference.azure_gpt import generate_response
    elif "gemini" in model_name:
        from model_inference.openai_compatible import generate_response
    elif model_name in json.load(open("model_inference/vllm_model_list.json")):
        from model_inference.vllm_inference import generate_response
    else:
        raise ValueError(f"Invalid model name: {model_name}")
    generate_response(model_name=model_name,
                    prompt=prompt,
                    queries=queries, 
                    output_path=output_path,
                    n = n,
                    **pi_options)
        
prompt_dict = {
    "cot": COT_PROMPT,
}

def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL,
                        help=f"Model/backend (default: {DEFAULT_MODEL})")
    parser.add_argument('--thinking', choices=('off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'),
                        default=None, help="Pi reasoning level: high for named models; session level for pi/current")
    parser.add_argument('--prompt', type=str, default="cot")
    parser.add_argument('--data_path', type=str, required=True)
    parser.add_argument('--output_dir', type=str, default="outputs")
    parser.add_argument("--api_base",type=str,default="")
    parser.add_argument("--max_num",type=int,default=5)
    parser.add_argument("--n",type=int,default=1)
    parser.add_argument("--overwrite",action="store_true", default=False)

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    model_name = args.model

    try:
        prompt = prompt_dict[args.prompt]
    except KeyError:
        print("Invalid prompt")
        sys.exit(1)


    os.makedirs(args.output_dir, exist_ok=True)
        
    data_path_suffix = args.data_path.split("/")[-1].split(".")[0]
    output_dir = os.path.join(args.output_dir, f"{data_path_suffix}_{args.prompt}")
    os.makedirs(output_dir, exist_ok=True)
    
    output_name = model_name.split("/")[-1]

    output_path = os.path.join(output_dir, f"{output_name}.json")


    queries = json.load(open(args.data_path, "r"))
    if args.max_num > 0:
        queries = queries[:args.max_num]

    if os.path.exists(output_path) and args.overwrite:
        orig_output = json.load(open(output_path, "r"))
        if len(orig_output) >= len(queries):
            print(f"Output file {output_path} already exists. Skipping.")
            sys.exit(0)
        else:
            print(f"Overwrite {output_path}")

    print(f"=========Running {args.model}=========\n")
    main(
        model_name = args.model, 
        prompt = prompt, 
        queries = queries, 
        output_path = output_path,
        n = args.n,
        thinking = args.thinking)
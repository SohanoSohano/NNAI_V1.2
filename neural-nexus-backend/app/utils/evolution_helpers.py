# app/utils/evolution_helpers.py
# Contains helper functions for the Celery evolution task.

import torch
import torch.nn as nn
import numpy as np
import os
import importlib.util
import time
import random
import logging # Import logging

logger = logging.getLogger(__name__) # Setup logger for this module

# --- Utility Functions (Model Loading, Weight Handling, Evaluation) ---

def flatten_weights(model):
    """ Flattens all model parameters into a single numpy vector. """
    try:
        weights = []
        for param in model.parameters():
            if param.requires_grad:
                # Ensure tensor is on CPU before converting to numpy
                weights.append(param.data.cpu().numpy().flatten())
        if not weights:
            logger.warning("No trainable parameters found in the model to flatten.")
            return np.array([]) # Return empty array instead of raising error immediately
        return np.concatenate(weights)
    except Exception as e:
        logger.error(f"Error during weight flattening: {e}", exc_info=True)
        raise

def load_weights_from_flat(model, flat_weights):
    """ Loads flattened weights back into a model instance. """
    try:
        offset = 0
        if not isinstance(flat_weights, np.ndarray):
            flat_weights = np.array(flat_weights)
        # Ensure flat_weights is float32 for torch conversion
        flat_weights_tensor = torch.from_numpy(flat_weights.astype(np.float32))
        model_device = next(model.parameters()).device # Get target device from model
        
        total_elements_in_model = sum(p.numel() for p in model.parameters() if p.requires_grad)
        if total_elements_in_model != len(flat_weights_tensor):
             logger.warning(f"Size mismatch: Model requires {total_elements_in_model} elements, but flat_weights has {len(flat_weights_tensor)}. Check architecture.")
             # Optionally raise error or proceed cautiously
             # raise ValueError("Model structure does not match flat_weights size.")

        for param in model.parameters():
            if param.requires_grad:
                numel = param.numel()
                param_shape = param.size()
                # Check if we have enough weights left
                if offset + numel > len(flat_weights_tensor):
                    logger.error(f"Shape mismatch: Not enough data in flat_weights (len {len(flat_weights_tensor)}) to fill parameter {param_shape} (needs {numel} at offset {offset})")
                    # Decide how to handle: raise error, break, or pad? Raising is safest.
                    raise ValueError(f"Shape mismatch loading weights for shape {param_shape}")

                param_slice = flat_weights_tensor[offset:offset + numel].view(param_shape).to(model_device)
                with torch.no_grad(): # Ensure no gradient tracking during data copy
                    param.data.copy_(param_slice)
                offset += numel

        if offset != len(flat_weights_tensor):
            # This warning might occur if the earlier size check passed but logic failed
            logger.warning(f"Potential Size mismatch after loading weights. Offset {offset} != flat_weights length {len(flat_weights_tensor)}.")

    except Exception as e:
        logger.error(f"Error loading weights from flat vector: {e}", exc_info=True)
        raise

def load_pytorch_model(model_definition_path, class_name, state_dict_path, device, *model_args, **model_kwargs):
    """ Loads the model class, instantiates it, and loads the state_dict. """
    try:
        # Normalize path for safety
        norm_model_path = os.path.normpath(model_definition_path)
        if not os.path.exists(norm_model_path):
             raise FileNotFoundError(f"Model definition file not found at {norm_model_path}")

        module_name = f"model_module_{random.randint(1000, 9999)}" # Avoid name collisions
        spec = importlib.util.spec_from_file_location(module_name, norm_model_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for module at {norm_model_path}")

        model_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model_module) # Execute module code

        if not hasattr(model_module, class_name):
            # List available classes for easier debugging
            available_classes = [name for name, obj in model_module.__dict__.items() if isinstance(obj, type)]
            raise AttributeError(f"Class '{class_name}' not found in {norm_model_path}. Available classes: {available_classes}")

        ModelClass = getattr(model_module, class_name)
        logger.info(f"Instantiating model '{class_name}' with args: {model_args}, kwargs: {model_kwargs}")
        model = ModelClass(*model_args, **model_kwargs)
        model.to(device) # Move model to device

        if state_dict_path:
            norm_weights_path = os.path.normpath(state_dict_path)
            if os.path.exists(norm_weights_path):
                logger.info(f"Loading state_dict from: {norm_weights_path}")
                try:
                    # Load state dict mapping to the model's device
                    state_dict = torch.load(norm_weights_path, map_location=device)
                    model.load_state_dict(state_dict)
                    logger.info("State_dict loaded successfully.")
                except Exception as load_err:
                    logger.error(f"Error loading state_dict (check architecture/keys): {load_err}", exc_info=True)
                    # Decide if this should be fatal or just a warning
                    # raise
            else:
                logger.warning(f"state_dict path '{norm_weights_path}' provided but not found.")
        else:
            logger.info("No state_dict path provided. Using model's initial weights.")

        model.eval() # Set model to evaluation mode
        return model
    except Exception as e:
        logger.error(f"Error in load_pytorch_model: {e}", exc_info=True)
        raise

def load_task_eval_function(task_module_path):
    """ Loads the fitness evaluation function from a specified file. """
    try:
        norm_eval_path = os.path.normpath(task_module_path)
        if not os.path.exists(norm_eval_path):
            raise FileNotFoundError(f"Evaluation script not found at {norm_eval_path}")

        module_name = f"eval_module_{random.randint(1000, 9999)}"
        spec = importlib.util.spec_from_file_location(module_name, norm_eval_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for module at {norm_eval_path}")

        task_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(task_module)

        # Standardize the function name to look for
        eval_func_name = 'evaluate_model' # Changed from 'evaluate_network_on_task'
        if not hasattr(task_module, eval_func_name):
             alt_func_name = 'evaluate_network_on_task' # Check for old name as fallback
             if hasattr(task_module, alt_func_name):
                 logger.warning(f"Found old eval func name '{alt_func_name}'. Recommend renaming to '{eval_func_name}'.")
                 eval_func_name = alt_func_name
             else:
                 raise AttributeError(f"Function '{eval_func_name}' not found in {norm_eval_path}")

        logger.info(f"Loaded evaluation function '{eval_func_name}' from {norm_eval_path}")
        return getattr(task_module, eval_func_name)
    except Exception as e:
        logger.error(f"Error loading task evaluation function: {e}", exc_info=True)
        raise

def evaluate_population_step(population_weights, model_definition_path, class_name, task_eval_func, device, model_args, model_kwargs):
    """ Evaluates the fitness of each individual in the population for one generation. """
    fitness_scores = []
    num_individuals = len(population_weights)
    evaluation_times = []

    logger.info(f"Evaluating {num_individuals} individuals...")
    # Pre-load the model class once to avoid repeated module loading
    try:
        module_name = f"model_module_{random.randint(1000, 9999)}"
        spec = importlib.util.spec_from_file_location(module_name, model_definition_path)
        model_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model_module)
        ModelClass = getattr(model_module, class_name)
    except Exception as e:
         logger.error(f"Failed to preload ModelClass '{class_name}': {e}", exc_info=True)
         raise # Cannot proceed without the class

    for i, flat_weights in enumerate(population_weights):
        individual_start_time = time.time()
        current_model = None
        try:
            # Instantiate model using preloaded class
            current_model = ModelClass(*model_args, **model_kwargs)
            current_model.to(device)
            load_weights_from_flat(current_model, flat_weights)
            current_model.eval()

            # Call the evaluation function (standardized name)
            # The eval function needs to accept model and config dict
            eval_config = {"device": device} # Pass device in config
            fitness = task_eval_func(current_model, eval_config)

            if not isinstance(fitness, (float, int)):
                logger.warning(f"Individual {i+1} fitness func returned non-numeric ({type(fitness)}). Setting -inf.")
                fitness = -float('inf')
            fitness_scores.append(float(fitness))

        except Exception as e:
            logger.error(f"Error evaluating individual {i+1}: {e}", exc_info=True) # Log full traceback for eval errors
            fitness_scores.append(-float('inf'))
        finally:
            # Cleanup model instance
            del current_model
            if device.type == 'cuda':
                torch.cuda.empty_cache()
            eval_time = time.time() - individual_start_time
            evaluation_times.append(eval_time)

    avg_eval_time = np.mean(evaluation_times) if evaluation_times else 0
    logger.info(f"Finished population evaluation. Avg time/individual: {avg_eval_time:.3f}s")
    return fitness_scores

# --- Genetic Algorithm Operators ---

# --- Selection Operators ---

# Renamed from original 'select_parents'
def select_parents_tournament(population_weights: list[np.ndarray], fitness_scores: list[float], num_parents: int, tournament_size: int = 3) -> list[np.ndarray]:
    """ Selects parents using tournament selection. """
    parents = []
    population_size = len(population_weights)
    if population_size == 0: return []
    if num_parents <= 0: return []

    # Ensure tournament size is valid
    actual_tournament_size = max(2, min(population_size, tournament_size))

    valid_indices = [i for i, f in enumerate(fitness_scores) if f > -float('inf')]
    if not valid_indices:
        logger.warning("All individuals failed evaluation. Cannot select parents via tournament.")
        return []

    num_valid = len(valid_indices)

    for _ in range(num_parents):
        # Sample participants, ensuring we don't try to sample more than available valid individuals
        current_tournament_participants_count = min(num_valid, actual_tournament_size)
        if current_tournament_participants_count < 1:
            logger.warning("No valid individuals left for tournament selection.")
            break # Stop trying to select more parents
        
        # Sample WITH replacement if fewer valid individuals than tournament size, otherwise without
        replace_sample = num_valid < actual_tournament_size
        tournament_indices = np.random.choice(valid_indices, size=current_tournament_participants_count, replace=replace_sample).tolist()

        winner_idx_in_population = -1
        best_fitness_in_tournament = -float('inf')
        for idx in tournament_indices:
            if fitness_scores[idx] > best_fitness_in_tournament:
                best_fitness_in_tournament = fitness_scores[idx]
                winner_idx_in_population = idx

        if winner_idx_in_population != -1:
            parents.append(population_weights[winner_idx_in_population])
        elif valid_indices: # Fallback if selection failed but candidates existed
            logger.warning("Could not select winner in tournament. Picking random valid individual.")
            parents.append(population_weights[random.choice(valid_indices)])

    return parents

# NEW: Roulette Wheel Selection
def select_parents_roulette(population: list[np.ndarray], fitness_scores: list[float], num_parents: int) -> list[np.ndarray]:
    """
    Selects parents using Roulette Wheel selection based on fitness scores.
    Handles non-negative fitness scores. If all scores are <= 0, uses uniform random selection.
    """
    if not population or not fitness_scores or len(population) != len(fitness_scores):
        raise ValueError("Population and fitness_scores must be non-empty and have the same length.")
    if num_parents <= 0: return []
    if num_parents > len(population): num_parents = len(population)

    fitness_np = np.array(fitness_scores, dtype=np.float64) # Use float64 for precision

    # Handle case where all fitness scores are invalid (-inf)
    valid_indices = np.where(fitness_np > -np.inf)[0]
    if len(valid_indices) == 0:
         logger.warning("All individuals have invalid fitness. Selecting parents uniformly.")
         indices = np.random.choice(len(population), size=num_parents, replace=True)
         return [population[i] for i in indices]

    # Consider only valid fitness scores for probability calculation
    valid_fitness = fitness_np[valid_indices]

    # If all valid scores are non-positive, select uniformly among valid individuals
    if np.all(valid_fitness <= 0):
        logger.warning("All valid fitness scores are <= 0. Selecting parents uniformly among valid.")
        selected_valid_indices = np.random.choice(valid_indices, size=num_parents, replace=True)
        return [population[i] for i in selected_valid_indices]

    # Shift valid fitness scores so the minimum is slightly above zero
    min_valid_fitness = np.min(valid_fitness)
    # Use a small epsilon relative to the scale of fitness scores if possible, or fixed small value
    epsilon = 1e-9
    if min_valid_fitness <= 0:
        shifted_fitness = valid_fitness - min_valid_fitness + epsilon
    else:
        shifted_fitness = valid_fitness # Already positive

    total_fitness = np.sum(shifted_fitness)

    if total_fitness <= 0: # Fallback if sum is still zero (e.g., all scores were identical and <= 0)
         logger.warning("Total fitness is zero after shifting. Selecting parents uniformly among valid.")
         selected_valid_indices = np.random.choice(valid_indices, size=num_parents, replace=True)
         return [population[i] for i in selected_valid_indices]

    probabilities = shifted_fitness / total_fitness
    # Ensure probabilities sum to 1 (handle potential float precision issues)
    probabilities /= np.sum(probabilities)

    # Perform selection using numpy's choice on the *indices* of the valid population
    selected_indices_in_valid_array = np.random.choice(len(valid_indices), size=num_parents, replace=True, p=probabilities)
    # Map back to the original population indices
    selected_original_indices = valid_indices[selected_indices_in_valid_array]

    selected_parents = [population[i] for i in selected_original_indices]
    return selected_parents

# --- Crossover Operators ---

# Renamed from original 'crossover'
def crossover_average(parent1: np.ndarray, parent2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """ Simple average crossover for weight vectors. Returns two identical children. """
    p1 = np.asarray(parent1) # Ensure numpy array
    p2 = np.asarray(parent2)
    if p1.shape != p2.shape:
        logger.warning(f"Parent shapes do not match for average crossover: {p1.shape} vs {p2.shape}. Returning copies.")
        return p1.copy(), p2.copy() # Return copies of parents on error
    child_weights = (p1 + p2) / 2.0
    # Return two copies of the averaged child
    return child_weights.copy(), child_weights.copy()

# NEW: One-Point Crossover
def crossover_one_point(parent1: np.ndarray, parent2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """ Performs one-point crossover on two parent weight vectors. """
    p1 = np.asarray(parent1)
    p2 = np.asarray(parent2)
    if p1.shape != p2.shape:
        logger.warning(f"Parent shapes do not match for one-point crossover: {p1.shape} vs {p2.shape}. Returning copies.")
        return p1.copy(), p2.copy()

    size = p1.size
    if size < 2: # Crossover requires at least 2 elements
        return p1.copy(), p2.copy()

    # Choose crossover point (exclusive of the first and last element indices)
    crossover_point = random.randint(1, size - 1)

    child1_weights = np.concatenate((p1[:crossover_point], p2[crossover_point:]))
    child2_weights = np.concatenate((p2[:crossover_point], p1[crossover_point:]))

    return child1_weights, child2_weights

# NEW: Uniform Crossover
def crossover_uniform(parent1: np.ndarray, parent2: np.ndarray, crossover_prob: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """ Performs Uniform Crossover on two parent weight vectors. """
    p1 = np.asarray(parent1)
    p2 = np.asarray(parent2)
    if p1.shape != p2.shape:
        logger.warning(f"Parent shapes do not match for uniform crossover: {p1.shape} vs {p2.shape}. Returning copies.")
        return p1.copy(), p2.copy()

    size = p1.size
    child1_weights = p1.copy()
    child2_weights = p2.copy()

    # Create a mask of random numbers
    swap_mask = np.random.rand(size) < crossover_prob

    # Apply the mask to swap genes
    # Use np.where for potentially better performance or clarity
    child1_weights = np.where(swap_mask, p2, p1)
    child2_weights = np.where(swap_mask, p1, p2)
    # Or using direct assignment (often just as fast for numpy):
    # child1_weights[swap_mask] = p2[swap_mask]
    # child2_weights[swap_mask] = p1[swap_mask]

    return child1_weights, child2_weights

# --- Mutation Operators ---

# Renamed from original 'mutate'
def mutate_gaussian(weights: np.ndarray, mutation_rate: float, mutation_strength: float) -> np.ndarray:
    """ Adds Gaussian noise to a fraction of weights based on mutation rate. """
    if not isinstance(weights, np.ndarray): weights = np.array(weights)
    if mutation_rate <= 0 or mutation_strength <= 0:
        return weights.copy() # Return copy even if no mutation

    mutated_weights = weights.copy()
    num_weights = weights.size
    num_weights_to_mutate = int(num_weights * mutation_rate)

    # Ensure at least one mutation if rate > 0 and weights exist
    if num_weights_to_mutate == 0 and mutation_rate > 0 and num_weights > 0:
        num_weights_to_mutate = 1

    if num_weights_to_mutate > 0:
        # Ensure we don't try to choose more indices than available
        num_weights_to_mutate = min(num_weights_to_mutate, num_weights)
        indices_to_mutate = np.random.choice(num_weights, num_weights_to_mutate, replace=False)

        # Generate noise of the correct dtype
        noise = np.random.normal(0, mutation_strength, size=num_weights_to_mutate).astype(mutated_weights.dtype)
        mutated_weights[indices_to_mutate] += noise

    return mutated_weights

# NEW: Uniform Random Mutation
def mutate_uniform_random(weights: np.ndarray, mutation_rate: float, mutation_strength: float = 0.1, value_range=(-1.0, 1.0)) -> np.ndarray:
    """
    Mutates weights by replacing selected genes with a new random value
    drawn uniformly from a specified range. mutation_strength is ignored here.
    """
    if not isinstance(weights, np.ndarray): weights = np.array(weights)
    if mutation_rate <= 0:
        return weights.copy() # Return copy even if no mutation

    mutated_weights = weights.copy()
    num_weights = weights.size
    min_val, max_val = value_range

    # Create a mask based on mutation rate
    mutation_mask = np.random.rand(num_weights) < mutation_rate

    # Generate new random values for the genes to be mutated
    num_mutations = np.sum(mutation_mask)
    if num_mutations > 0:
        new_values = np.random.uniform(min_val, max_val, size=num_mutations).astype(mutated_weights.dtype)
        # Apply the new values using the mask
        mutated_weights[mutation_mask] = new_values

    return mutated_weights

# --- End of Helper Functions ---

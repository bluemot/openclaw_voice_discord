# Addition to hound_tools.py - find_callers function
# This should be added before submit_final_answer function

    def find_callers(
        func_name: Annotated[str, Field(..., description="The name of the function to find callers for (who calls this function?).")],
        file_pattern: Annotated[str, Field("*.[ch]", description="File pattern to search (e.g., *.c, *.py).")] = "*.[ch]"
    ) -> str:
        """
        Find all functions that CALL this function (REVERSE direction: callers -> target).
        
        This is the OPPOSITE of analyze_function_deeply.
        Use this when you need to trace UP the call chain (who calls this function?).
        
        Mixed strategy: Graph Query (if available) + Hound Search (always works).
        
        Args:
            func_name: The function name to find callers for.
            file_pattern: File pattern to search (default: C/C++ files).
        
        Returns:
            JSON with list of callers and their locations.
        """
        results = {
            "intent": "find_callers",
            "function": func_name,
            "callers": [],
            "sources": []
        }
        
        # Layer 1: Graph Query (if Memgraph is available)
        graph_callers = []
        if ingestor and hasattr(ingestor, 'fetch_all'):
            try:
                query = """
                MATCH (caller:Function)-[r:CALLS]->(target:Function {name: $name})
                RETURN caller.name as name, caller.file as file, caller.line as line
                """
                graph_results = ingestor.fetch_all(query, {"name": func_name})
                
                for row in graph_results or []:
                    caller_info = {
                        "name": row.get("name"),
                        "file": row.get("file"),
                        "line": row.get("line"),
                        "source": "graph"
                    }
                    if caller_info["name"]:
                        graph_callers.append(caller_info)
                
                if graph_callers:
                    logger.info(f"[Hound] Graph query found {len(graph_callers)} callers for {func_name}")
                    
            except Exception as e:
                logger.debug(f"[Hound] Graph query failed: {e}")
        
        # Layer 2: Hound Search (ripgrep)
        hound_callers = []
        try:
            search_pattern = f"{re.escape(func_name)}\\s*\\("
            cmd = ["rg", "-n", "-g", file_pattern, search_pattern]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=searcher.codebase_root)
            
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split("\n")
                
                for line in lines[:50]:
                    try:
                        parts = line.split(":", 2)
                        if len(parts) >= 3:
                            file_path = parts[0]
                            line_num = int(parts[1])
                            matching_line = parts[2].strip()
                            
                            # Extract caller name from context
                            caller_name = _extract_caller_from_context(file_path, line_num, func_name)
                            
                            if caller_name:
                                hound_callers.append({
                                    "name": caller_name,
                                    "file": file_path,
                                    "line": line_num,
                                    "context": matching_line[:100],
                                    "source": "hound"
                                })
                    except Exception as parse_err:
                        logger.debug(f"[Hound] Failed to parse line: {parse_err}")
                
                if hound_callers:
                    logger.info(f"[Hound] Hound search found {len(hound_callers)} callers for {func_name}")
                    
        except Exception as e:
            logger.debug(f"[Hound] Hound search failed: {e}")
        
        # Merge and deduplicate
        all_callers = []
        seen_names = set()
        
        for caller in graph_callers:
            if caller["name"] not in seen_names:
                all_callers.append(caller)
                seen_names.add(caller["name"])
        
        for caller in hound_callers:
            if caller["name"] not in seen_names:
                all_callers.append(caller)
                seen_names.add(caller["name"])
        
        results["callers"] = all_callers
        results["sources"] = list(set(c["source"] for c in all_callers))
        
        if all_callers:
            if len(all_callers) == 1:
                guidance = f"\n>>> CALLER RESOLVED: '{all_callers[0]['name']}' is the only caller."
            else:
                caller_names = [c['name'] for c in all_callers[:3]]
                guidance = f"\n>>> FOUND {len(all_callers)} CALLERS: {', '.join(caller_names)}{'...' if len(all_callers) > 3 else ''}. Each needs separate tracing."
            results["guidance"] = guidance
        
        return format_results_as_json(intent="find_callers", results=results)

    def _extract_caller_from_context(file_path: str, target_line: int, target_func: str) -> Optional[str]:
        """Extract caller function name by looking backwards from target line."""
        try:
            full_path = os.path.join(searcher.codebase_root, file_path)
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            for i in range(min(target_line, len(lines)) - 1, max(0, target_line - 100), -1):
                line = lines[i].strip()
                match = re.match(r'^[\w\s\*]+\s+(\w+)\s*\(', line)
                if match:
                    func_name = match.group(1)
                    if func_name not in ('if', 'while', 'for', 'switch', 'catch', 'return'):
                        return func_name
            
            for i in range(max(0, target_line - 10), min(target_line, len(lines))):
                line = lines[i].strip()
                match = re.match(r'^\s*(\w+)\s*\(', line)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception as e:
            logger.debug(f"[Hound] Failed to extract caller: {e}")
            return None
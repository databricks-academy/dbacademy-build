from dbacademy_gems import dbgems
from dbacademy_courseware import validate_type
from dbacademy_courseware.dbbuild import common

class Translator:
    from dbacademy_courseware.dbbuild import BuildConfig

    def __init__(self, build_config: BuildConfig):
        from dbacademy_courseware.dbbuild import BuildConfig

        self.__validated = False  # By default, we are not validated

        self.build_config = validate_type(build_config, "build_config", BuildConfig)
        # Copied from build_config
        self.username = build_config.username
        self.client = build_config.client
        self.notebooks = build_config.notebooks
        self.build_name = build_config.build_name

        # Defined in select_language
        self.lang_code = None
        self.version = None
        self.core_version = None
        self.common_language = None
        self.resources_folder = None

        # Defined in rest_repo
        self.source_branch = None
        self.source_dir = None
        self.source_repo_url = None

        self.target_branch = None
        self.target_dir = None
        self.target_repo_url = None

        self.errors = []
        self.warnings = []
        self._select_i18n_language(build_config.source_repo)

    def _select_i18n_language(self, source_repo: str):
        from dbacademy_gems import dbgems

        self.resources_folder = f"{source_repo}/Resources"

        resources = self.client.workspace().ls(self.resources_folder)
        self.language_options = [r.get("path").split("/")[-1] for r in resources]
        self.language_options = [p for p in self.language_options if not p.startswith("english-") and not p.startswith("_")]
        self.language_options.sort()

        dbgems.dbutils.widgets.dropdown("i18n_language",
                                        self.language_options[0],
                                        self.language_options,
                                        "i18n Language")

        self.i18n_language = dbgems.get_parameter("i18n_language", None)
        assert self.i18n_language is not None, f"The i18n language must be specified."
        assert self.i18n_language in self.language_options, f"The selected version must be one of {self.language_options}, found \"{self.i18n_language}\"."

        for notebook in self.notebooks.values():
            notebook.i18n_language = self.i18n_language

        # Include the i18n code in the version.
        # This hack just happens to work for japanese and korean
        self.lang_code = self.i18n_language[0:2].upper()
        self.common_language, self.core_version = self.i18n_language.split("-")
        self.core_version = self.core_version[1:]
        self.version = f"{self.core_version}-{self.lang_code}"

        # Include the i18n code in the version.
        # This hack just happens to work for japanese and korean
        self.common_language = self.i18n_language.split("-")[0]

    def __reset_source_repo(self, source_dir: str = None, source_repo_url: str = None, source_branch: str = None):

        self.source_branch = source_branch or f"published-v{self.core_version}"
        self.source_dir = source_dir or f"/Repos/Temp/{self.username}-{self.build_name}-english_{self.source_branch}"
        self.source_repo_url = source_repo_url or f"https://github.com/databricks-academy/{self.build_name}-english.git"

        common.reset_git_repo(client=self.client,
                              directory=self.source_dir,
                              repo_url=self.source_repo_url,
                              branch=self.source_branch,
                              which="source")

    def __reset_target_repo(self, target_dir: str = None, target_repo_url: str = None, target_branch: str = None):

        self.target_branch = target_branch or "published"
        self.target_dir = target_dir or f"/Repos/Temp/{self.build_name}"
        self.target_repo_url = target_repo_url or f"https://github.com/databricks-academy/{self.build_name}-{self.common_language}.git"

        common.reset_git_repo(client=self.client,
                              directory=self.target_dir,
                              repo_url=self.target_repo_url,
                              branch=self.target_branch,
                              which="target")

    def validate(self):
        self.__reset_source_repo()
        self.__reset_target_repo()
        print(f"version:          {self.version}")
        print(f"core_version:     {self.core_version}")
        print(f"common_language:  {self.common_language}")
        print(f"resources_folder: {self.resources_folder}")

        self.__validated = True

    def _load_i18n_source(self, path):
        import os

        if path.startswith("Solutions/"): path = path[10:]
        if path.startswith("Includes/"): return ""

        i18n_source_path = f"/Workspace{self.resources_folder}/{self.i18n_language}/{path}.md"
        assert os.path.exists(i18n_source_path), f"Cannot find {i18n_source_path}"

        with open(f"{i18n_source_path}") as f:
            source = f.read()
            source = source.replace("<hr />\n--i18n-", "<hr>--i18n-")
            source = source.replace("<hr sandbox />\n--i18n-", "<hr sandbox>--i18n-")
            return source

    # noinspection PyMethodMayBeStatic
    def _load_i18n_guid_map(self, path: str, i18n_source: str):
        import re
        from dbacademy_courseware.dbpublish import NotebookDef

        if i18n_source is None:
            return dict()

        i18n_guid_map = dict()

        # parts = re.split(r"^<hr>--i18n-", i18n_source, flags=re.MULTILINE)
        parts = re.split(r"^<hr>--i18n-|^<hr sandbox>--i18n-", i18n_source, flags=re.MULTILINE)

        name = parts[0].strip()[3:]
        path = path[10:] if path.startswith("Solutions/") else path
        if not path.startswith("Includes/"):
            assert name == path, f"Expected the notebook \"{path}\", found \"{name}\""

        for part in parts[1:]:
            guid, value = NotebookDef.parse_guid_and_value(part)

            i18n_guid_map[guid] = value

        return i18n_guid_map

    @property
    def validated(self):
        return self.__validated

    # noinspection PyMethodMayBeStatic
    def __extract_i18n_guid(self, command):
        line_zero = command.strip().split("\n")[0]

        prefix = "<i18n value=\""
        pos_a = line_zero.find(prefix)
        if pos_a == -1:
            return None, line_zero

        pos_b = line_zero.find("/>")
        guid = f"--i18n-{line_zero[pos_a+len(prefix):pos_b - 1]}"
        return guid, line_zero

    def publish_notebooks(self):
        from datetime import datetime
        from dbacademy_courseware.dbpublish import Publisher, NotebookDef
        from dbacademy_courseware import get_workspace_url

        assert self.validated, f"Cannot publish until the validator's configuration passes validation. Ensure that Translator.validate() was called and that all assignments passed"

        print(f"Publishing translated version of {self.build_name}, {self.version}")
        print(f"...Removing files from target directories")
        common.clean_target_dir(self.client, self.target_dir, verbose=False)

        prefix = len(self.source_dir) + 1
        source_files = [f.get("path")[prefix:] for f in self.client.workspace.ls(self.source_dir, recursive=True)]
        print(f"...Processing {len(source_files)} files:")

        # We have to first create the directory before writing to it.
        # Processing them first, once and only once, avoids duplicate REST calls.
        print(f"...Pre-creating directory structures")
        processed_directory = []
        for file in source_files:
            target_notebook_path = f"{self.target_dir}/{file}"
            if target_notebook_path not in processed_directory:
                processed_directory.append(target_notebook_path)
                target_notebook_dir = "/".join(target_notebook_path.split("/")[:-1])
                self.client.workspace.mkdirs(target_notebook_dir)

        print("\nProcessing notebooks:")
        for file in source_files:
            print(f"   /{file}")
            source = self._load_i18n_source(file)
            i18n_guid_map = self._load_i18n_guid_map(file, source)

            # Compute the source and target directories
            source_notebook_path = f"{self.source_dir}/{file}"
            target_notebook_path = f"{self.target_dir}/{file}"

            source_info = self.client.workspace().get_status(source_notebook_path)
            language = source_info["language"].lower()
            cmd_delim = NotebookDef.get_cmd_delim(language)
            cm = NotebookDef.get_comment_marker(language)

            raw_source = self.client.workspace().export_notebook(source_notebook_path)
            raw_lines = raw_source.split("\n")
            header = raw_lines.pop(0)
            source = "\n".join(raw_lines)

            if file.startswith("Includes/"):
                # Write the original notebook to the target directory
                self.client.workspace.import_notebook(language=language.upper(),
                                                      notebook_path=target_notebook_path,
                                                      content=raw_source,
                                                      overwrite=True)
                continue

            commands = source.split(cmd_delim)
            new_commands = [commands.pop(0)]

            for i, command in enumerate(commands):
                command = command.strip()
                guid, line_zero = self.__extract_i18n_guid(command)
                if guid is None:
                    new_commands.append(command)                            # No GUID, it's %python or other type of command, not MD
                else:
                    assert guid in i18n_guid_map, f"The GUID \"{guid}\" was not found in \"{file}\"."
                    replacements = i18n_guid_map[guid].strip().split("\n")  # Get the replacement text for the specified GUID
                    cmd_lines = [f"{cm} MAGIC {x}" for x in replacements]   # Prefix the magic command to each line

                    lines = [line_zero, ""]                                 # The first line doesn't exist in the guid map
                    lines.extend(cmd_lines)                                 # Convert to a set of lines and append

                    new_command = "\n".join(lines)                          # Combine all the lines into a new command
                    new_commands.append(new_command.strip())                # Append the new command to set of commands

            new_source = f"{header}\n"                           # Add the Databricks Notebook Header
            new_source += f"\n{cmd_delim}\n".join(new_commands)  # Join all the new_commands into one

            # Update the built_on and version_number - typically only found in the Version Info notebook.
            built_on = datetime.now().strftime("%b %-d, %Y at %H:%M:%S UTC")
            new_source = new_source.replace("{{built_on}}", built_on)
            new_source = new_source.replace("{{version_number}}", self.version)

            # Write the new notebook to the target directory
            self.client.workspace.import_notebook(language=language.upper(),
                                                  notebook_path=target_notebook_path,
                                                  content=new_source,
                                                  overwrite=True)

        html = f"""<html><body style="font-size:16px">
                     <div><a href="{get_workspace_url()}#workspace{self.target_dir}/{Publisher.VERSION_INFO_NOTEBOOK}" target="_blank">See Published Version</a></div>
                   </body></html>"""

        dbgems.display_html(html)

    def create_dbcs(self):
        from dbacademy_gems import dbgems

        assert self.validated, f"Cannot create DBCs until the publisher passes validation. Ensure that Publisher.validate() was called and that all assignments passed."

        print(f"Exporting DBC from \"{self.target_dir}\"")
        data = self.client.workspace.export_dbc(self.target_dir)

        common.write_file(data=data,
                          overwrite=False,
                          target_name="Distributions system (versioned)",
                          target_file=f"dbfs:/mnt/secured.training.databricks.com/distributions/{self.build_name}/v{self.version}/{self.build_name}-v{self.version}-notebooks.dbc")

        common.write_file(data=data,
                          overwrite=False,
                          target_name="Distributions system (latest)",
                          target_file=f"dbfs:/mnt/secured.training.databricks.com/distributions/{self.build_name}/vLATEST-{self.lang_code}/notebooks.dbc")

        common.write_file(data=data,
                          overwrite=True,
                          target_name="workspace-local FileStore",
                          target_file=f"dbfs:/FileStore/tmp/{self.build_name}-v{self.version}/{self.build_name}-v{self.version}-notebooks.dbc")

        url = f"/files/tmp/{self.build_name}-v{self.version}/{self.build_name}-v{self.version}-notebooks.dbc"
        dbgems.display_html(f"""<html><body style="font-size:16px"><div><a href="{url}" target="_blank">Download DBC</a></div></body></html>""")

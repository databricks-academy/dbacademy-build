from typing import List
from .notebook_def_class import NotebookDef
from dbacademy_courseware.dbbuild import BuildConfig
from dbacademy_courseware import validate_type, print_deprecated_msg


class Publisher:

    VERSION_INFO_NOTEBOOK = "Version Info"

    KEEPERS = [".gitignore", "README.md", "LICENSE", "docs"]

    def __init__(self, build_config: BuildConfig):

        self.__validated = False             # By default, we are not validated
        self.__validated_repo_reset = True   # By default repo is valid (unless invoked)

        self.build_config = validate_type(build_config, "build_config", BuildConfig)

        self.client = build_config.client
        self.version = build_config.version
        self.core_version = build_config.core_version
        self.build_name = build_config.build_name

        self.source_dir = build_config.source_dir
        self.target_dir = f"{self.build_config.source_repo}/Published/{self.build_config.name} - v{self.build_config.version}"
        self.target_repo_url = None
        self.temp_repo_dir = f"/Repos/Temp"
        self.temp_work_dir = f"/Workspace/Users/{build_config.username}/Temp"
        self.username = build_config.username

        self.i18n = build_config.i18n
        self.i18n_resources_dir = f"{build_config.source_repo}/Resources/{build_config.i18n_language}"
        self.i18n_language = build_config.i18n_language

        if build_config.i18n_language is None:
            self.common_language = "english"
        else:
            # Include the i18n code in the version.
            # This hack just happens to work for japanese and korean
            self.common_language = build_config.i18n_language.split("-")[0]

        self.notebooks = []
        self._init_notebooks(build_config.notebooks.values())

        self.white_list = build_config.white_list
        self.black_list = build_config.black_list
        self._validate_white_black_list()

    def _init_notebooks(self, notebooks):
        from datetime import datetime

        for notebook in notebooks:
            assert type(notebook) == NotebookDef, f"Expected the parameter \"notebook\" to be of type \"NotebookDef\", found \"{type(notebook)}\"."

            # Add the universal replacements
            notebook.replacements["version_number"] = self.version
            notebook.replacements["built_on"] = datetime.now().strftime("%b %-d, %Y at %H:%M:%S UTC")

            self.notebooks.append(notebook)

    def _validate_white_black_list(self):
        if self.white_list or self.black_list:
            assert self.white_list is not None, "The white_list must be specified when specifying a black_list"
            assert self.black_list is not None, "The black_list must be specified when specifying a white_list"

            notebook_paths = [n.path for n in self.notebooks]

            # Validate white and black lists
            for path in self.white_list:
                assert path not in self.black_list, f"The white-list path \"{path}\" was also found in the black-list."
                assert path in notebook_paths, f"The white-list path \"{path}\" does not exist in the complete set of notebooks.\n{notebook_paths}"

            for path in self.black_list:
                assert path not in self.white_list, f"The black-list path \"{path}\" was also found in the white-list."
                assert path in notebook_paths, f"The black-list path \"{path}\" does not exist in the complete set of notebooks.\n{notebook_paths}"

            for path in notebook_paths:
                assert path in self.white_list or path in self.black_list, f"The notebook \"{path}\" was not found in either the white-list or black-list."

    # def create_new_resource_message(self, language, resource_dir, domain="curriculum-dev.cloud.databricks.com", workspace_id="3551974319838082"):
    #     return f"""
    #             <body>
    #                 <p><a href="https://{domain}/?o={workspace_id}#workspace{resource_dir}/{language}/{self.version_info_notebook}.md" target="_blank">Resource Bundle: {language}</a></p>
    #             </body>"""

    def create_resource_bundle(self, folder_name: str = None, target_dir: str = None):
        from dbacademy_gems import dbgems

        if self.i18n_language is not None:
            print(f"Print skipping generation of resource bundle for non-english release, {self.i18n_language}")
            return False

        folder_name = folder_name or f"english-v{self.build_config.version}"
        target_dir = target_dir or f"{self.build_config.source_repo}/Resources"

        for notebook in self.notebooks:
            notebook.create_resource_bundle(folder_name, self.source_dir, target_dir)

        html = f"""<body><p><a href="/#workspace{target_dir}/{folder_name}/{Publisher.VERSION_INFO_NOTEBOOK}.md" target="_blank">Resource Bundle: {folder_name}</a></p></body>"""
        dbgems.display_html(html)

        return True

    def publish_notebooks(self, *, verbose=False, debugging=False, **kwargs):

        assert self.validated, f"Cannot publish notebooks until the publisher passes validation. Ensure that Publisher.validate() was called and that all assignments passed."

        from dbacademy_gems import dbgems
        from dbacademy_courseware import get_workspace_url

        if "mode" in kwargs:
            print_deprecated_msg("The parameter \"mode\" has been deprecated.\nPlease remove the parameter.")

        found_version_info = False
        main_notebooks: List[NotebookDef] = []

        for notebook in self.notebooks:
            if self.black_list is None or notebook.path not in self.black_list:
                found_version_info = True if notebook.path == Publisher.VERSION_INFO_NOTEBOOK else found_version_info
                main_notebooks.append(notebook)

        assert found_version_info, f"The required notebook \"{Publisher.VERSION_INFO_NOTEBOOK}\" was not found."

        print(f"Source: {self.source_dir}")
        print(f"Target: {self.target_dir}")
        print()
        print("Arguments:")
        print(f"  verbose =   {verbose}")
        print(f"  debugging = {debugging}")

        if self.black_list is None:
            print(f"  exclude:    none")
        else:
            self.black_list.sort()
            print(f"\n  exclude:    {self.black_list[0]}")
            for path in self.black_list[1:]:
                print(f"              {path}")

        if self.white_list is None:
            print(f"  include:    none")
        else:
            self.white_list.sort()
            print(f"\n  include:    {self.white_list[0]}")
            for path in self.white_list[1:]:
                print(f"              {path}")

        # Now that we backed up the version-info, we can delete everything.
        target_status = self.client.workspace().get_status(self.target_dir)
        if target_status is not None:
            self.print_if(verbose, "-" * 80)
            Publisher.clean_target_dir(self.client, self.target_dir, verbose)

        for notebook in main_notebooks:
            notebook.publish(source_dir=self.source_dir,
                             target_dir=self.target_dir,
                             i18n_resources_dir=self.i18n_resources_dir,
                             verbose=verbose, 
                             debugging=debugging,
                             other_notebooks=self.notebooks)

        print("-"*80)
        print("All done!")

        html = f"""<html><body style="font-size:16px"><div><a href="{get_workspace_url()}#workspace{self.target_dir}/{Publisher.VERSION_INFO_NOTEBOOK}" target="_blank">See Published Version</a></div>"""
        for notebook in main_notebooks:
            if len(notebook.warnings) > 0:
                html += f"""<div style="font-weight:bold; margin-top:1em">{notebook.path}</div>"""
                for warning in notebook.warnings:
                    html += f"""<div style="white-space: pre-wrap">{warning.message}</div>"""
        html += """</table></body></html>"""

        dbgems.display_html(html)

    @staticmethod
    def clean_target_dir(client, target_dir: str, verbose):
        if verbose: print(f"Cleaning {target_dir}...")

        keepers = [f"{target_dir}/{k}" for k in Publisher.KEEPERS]

        for path in [p.get("path") for p in client.workspace.ls(target_dir) if p.get("path") not in keepers]:
            if verbose: print(f"...{path}")
            client.workspace().delete_path(path)

    def create_published_message(self):
        import urllib.parse
        from dbacademy_gems import dbgems

        name = self.build_config.name
        version = self.build_config.version
        source_repo = self.build_config.source_repo

        core_message = f"Change Log:\n"
        for entry in self.build_config.change_log:
            core_message += entry
            core_message += "\n"
        core_message += f"""
Release notes, course-specific requirements, issue-tracking, and test results for this course can be found in the course's GitHub repository at https://github.com/databricks-academy/{source_repo.split("/")[-1]}

Please feel free to reach out to me (via Slack) or anyone on the curriculum team should you have any questions."""

        email_body = urllib.parse.quote(core_message, safe="")
        slack_message = f"""@channel Published {name}, v{version}\n\n{core_message.strip()}"""

        content = "<div>"
        for group_name, group in self.build_config.publishing_info.items():
            content += f"""<div style="margin-bottom:1em">"""
            content += f"""<div style="font-size:16px;">{group_name}</div>"""
            for link_name, url in group.items():
                if url == "mailto:curriculum-announcements@databricks.com": url += f"?subject=Published {name}, v{version}&body={email_body}"
                content += f"""<li><a href="{url}" target="_blank" style="font-size:16px">{link_name}</a></li>"""
            content += "</div>"
        content += "</div>"

        rows = len(slack_message.split("\n"))+1
        html = f"""
        <body>
            {content}
            <textarea style="width:100%; padding:1em" rows={rows}>{slack_message}</textarea>
        </body>"""
        dbgems.display_html(html)

    @staticmethod
    def print_if(condition, text):
        if condition:
            print(text)

    def validate(self):
        print(f"Source: {self.source_dir}")
        print(f"Target: {self.target_dir}")

        print("\nChange Log:")
        for entry in self.build_config.change_log:
            print(f"  {entry}")

        self.__validated = True
        return

    @property
    def validated(self) -> bool:
        # Both have to be true to be considered validated.
        return self.__validated and self.__validated_repo_reset

    def reset_repo(self, target_dir: str, target_repo_url: str = None, branch: str = "published", **kwargs):
        print_deprecated_msg("Use Publisher.configure_target_repo() instead")

        return self.configure_target_repo(target_dir, target_repo_url, branch, **kwargs)

    def configure_target_repo(self, target_dir: str = None, target_repo_url: str = None, branch: str = "published", **kwargs):
        # Assume for now that we have failed. This overrides the default
        # of True meaning we have to succeed here to continue
        self.__validated_repo_reset = False

        new_target_dir = f"/Repos/Temp/{self.username}-{self.build_name}-{self.common_language}"
        if target_dir == new_target_dir: print_deprecated_msg(f"The value of the parameter \"target_dir\" is the same as the default value.\nConsider removing the parameter.")
        target_dir = target_dir or new_target_dir

        new_target_repo_url = f"https://github.com/databricks-academy/{self.build_name}-{self.common_language}.git"
        if target_repo_url == new_target_repo_url: print_deprecated_msg(f"The value of the parameter \"target_repo_url\" is the same as the default value.\nConsider removing the parameter.")
        target_repo_url = target_repo_url or new_target_repo_url

        if "target_url" in kwargs:
            print_deprecated_msg("The parameter \"target_url\" has been deprecated.\nUse \"target_repo_url\" instead.")
            target_repo_url = kwargs.get("target_url")

        self.target_dir = validate_type(target_dir, "target_dir", str)
        self.target_repo_url = validate_type(target_repo_url, "target_repo_url", str)

        print(f"Resetting git repo:")
        print(f" - Branch: \"{branch}\"")
        print(f" - Target: {self.target_dir}")
        print(f" - Source: {self.target_repo_url}")

        status = self.client.workspace().get_status(self.target_dir)

        if status is not None:
            target_repo_id = status["object_id"]
            self.client.repos().delete(target_repo_id)

        # Re-create the repo to progress in testing
        response = self.client.repos.create(path=self.target_dir, url=target_repo_url)
        repo_id = response.get("id")

        if response.get("branch") != branch:
            self.client.repos.update(repo_id=repo_id, branch=branch)

        results = self.client.repos.get(repo_id)
        current_branch = results.get("branch")

        assert branch == current_branch, f"Expected the new branch to be {branch}, found {current_branch}"

        self.__validated_repo_reset = True

    def publish_docs(self):
        import os, shutil
        from dbacademy_gems import dbgems
        from dbacademy_courseware import get_workspace_url

        source_docs_path = f"{self.build_config.source_repo}/docs"
        target_docs_path = f"{self.target_dir}/docs/v{self.build_config.version}"

        print(f"Source: {source_docs_path}")
        print(f"Target: {target_docs_path}")

        if os.path.exists(f"/Workspace/{target_docs_path}"):
            shutil.rmtree(f"/Workspace/{target_docs_path}")

        shutil.copytree(src=f"/Workspace/{source_docs_path}",
                        dst=f"/Workspace/{target_docs_path}")

        print("-" * 80)
        for file in os.listdir(f"/Workspace/{target_docs_path}"):
            print(file)

        html = f"""<html><body><p><a href="{get_workspace_url()}#workspace{target_docs_path}/index.html" target="_blank">Published Version</a></p></body></html>"""
        dbgems.display_html(html)

    def to_test_suite(self, test_type: str = None, keep_success: bool = False):
        from dbacademy_courseware.dbtest import TestSuite
        return TestSuite(build_config=self.build_config,
                         test_dir=self.target_dir,
                         test_type=test_type,
                         keep_success=keep_success)

    def _generate_html(self, notebook):
        import time
        from dbacademy_gems import dbgems

        if notebook.test_round < 2:
            return  # Skip for rounds 0 & 1

        start = int(time.time())

        path = f"../Source/{notebook.path}"
        dbgems.dbutils.notebook.run(path, timeout_seconds=60 * 5, arguments={
            "version": self.build_config.version,
            "generating_docs": True
        })

        print(f"Generated docs for \"{notebook.path}\"...({int(time.time()) - start} seconds)")

    def generate_docs(self):
        from multiprocessing.pool import ThreadPool

        with ThreadPool(len(self.build_config.notebooks)) as pool:
            pool.map(self._generate_html, self.build_config.notebooks.values())

    def create_dbc(self):
        print_deprecated_msg("Use Publisher.create_dbcs() instead")
        return self.create_dbcs()

    def create_dbcs(self):
        from dbacademy_gems import dbgems

        assert self.validated, f"Cannot create DBCs until the publisher passes validation. Ensure that Publisher.validate() was called and that all assignments passed."

        print(f"Exporting DBC from \"{self.target_dir}\"")
        data = self.build_config.client.workspace.export_dbc(self.target_dir)

        self.write_file(data=data,
                        overwrite=False,
                        target_name="Distributions system (versioned)",
                        target_file=f"dbfs:/mnt/secured.training.databricks.com/distributions/{self.build_config.build_name}/v{self.build_config.version}/{self.build_config.build_name}-v{self.build_config.version}.dbc")

        self.write_file(data=data,
                        overwrite=False,
                        target_name="Distributions system (latest)",
                        target_file=f"dbfs:/mnt/secured.training.databricks.com/distributions/{self.build_config.build_name}/vLATEST/notebooks.dbc")

        self.write_file(data=data,
                        overwrite=True,
                        target_name="workspace-local FileStore",
                        target_file=f"dbfs:/FileStore/tmp/{self.build_config.build_name}-v{self.build_config.version}/{self.build_config.build_name}-v{self.build_config.version}.dbc")

        url = f"/files/tmp/{self.build_config.build_name}-v{self.build_config.version}/notebooks.dbc"
        dbgems.display_html(f"""<html><body style="font-size:16px"><div><a href="{url}" target="_blank">Download DBC</a></div></body></html>""")

    @staticmethod
    def write_file(*, data: bytearray, target_file: str, overwrite: bool, target_name):
        import os
        print(f"\nWriting DBC to {target_name}:\n   {target_file}")

        target_file = target_file.replace("dbfs:/", "/dbfs/")

        if os.path.exists(target_file):
            # assert overwrite, f"Cannot overwrite existing file: {target_file}"
            # print(f"Removing existing file: {target_file}")
            os.remove(target_file)

        course_dir = "/".join(target_file.split("/")[:-2])
        if not os.path.exists(course_dir): os.mkdir(course_dir)

        version_dir = "/".join(target_file.split("/")[:-1])
        if not os.path.exists(version_dir): os.mkdir(version_dir)

        with open(target_file, "wb") as f:
            # print(f"Writing data: {target_file}")
            f.write(data)

    def get_validator(self):
        from .validator import Validator
        return Validator(self)

    @staticmethod
    def reset_git_repo(client, directory, repo_url, branch):

        print(f"Resetting git repo:")
        print(f" - Branch:  \"{branch}\"")
        print(f" - Directory: {directory}")
        print(f" - Repo URL:  {repo_url}")
        print()

        status = client.workspace().get_status(directory)

        if status is not None:
            target_repo_id = status["object_id"]
            client.repos().delete(target_repo_id)

        # Re-create the repo to progress in testing
        response = client.repos.create(path=directory, url=repo_url)
        repo_id = response.get("id")

        if response.get("branch") != branch:
            client.repos.update(repo_id=repo_id, branch=branch)

        results = client.repos.get(repo_id)
        current_branch = results.get("branch")

        assert branch == current_branch, f"Expected the new branch to be {branch}, found {current_branch}"

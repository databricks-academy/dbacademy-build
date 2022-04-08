from dbacademy.dbpublish.notebook_def_class import NotebookDef


class Publisher:
    def __init__(self, client, version: str, source_dir: str, target_dir: str):
        self.client = client
        self.version = version
        self.version_info_notebook_name = "Version Info"

        self.source_dir = source_dir
        self.target_dir = target_dir

        self.notebooks = []

    def add_all(self, notebooks):

        if type(notebooks) == dict:
            print(f"DEBUG: Converting dict to list in Publisher.add_all")
            notebooks = list(notebooks.values())

        for notebook in notebooks:
            self.add_notebook(notebook)

    def add_notebook(self, notebook):
        from datetime import datetime
        from dbacademy.dbpublish.notebook_def_class import NotebookDef

        assert type(notebook) == NotebookDef, f"""Expected the parameter "notebook" to be of type "NotebookDef", found "{type(notebook)}" """

        # Add the universal replacements
        notebook.replacements["version_number"] = self.version
        notebook.replacements["built_on"] = datetime.now().strftime("%b %-d, %Y at %H:%M:%S UTC")

        self.notebooks.append(notebook)

    def create_resource_bundle(self, language:str, target_dir:str):
        for notebook in self.notebooks:
            notebook.create_resource_bundle(language, self.source_dir, target_dir)

    def publish(self, testing, mode=None, verbose=False, debugging=False):
        version_info_notebook = None
        main_notebooks = []

        mode = str(mode).lower()
        expected_modes = ["delete", "overwrite", "no-overwrite"]
        assert mode in expected_modes, f"Expected mode {mode} to be one of {expected_modes}"

        for notebook in self.notebooks:
            if notebook.path == self.version_info_notebook_name:
                version_info_notebook = notebook
            else:
                main_notebooks.append(notebook)

        assert version_info_notebook is not None, f"""The required notebook "{self.version_info_notebook_name}" was not found."""

        print(f"Source: {self.source_dir}")
        print(f"Target: {self.target_dir}")
        print()
        print("Arguments:")
        print(f"  mode =      {mode}")
        print(f"  verbose =   {verbose}")
        print(f"  debugging = {debugging}")
        print(f"  testing =   {testing}")

        # Backup the version info in case we are just testing
        try:
            version_info_target = f"{self.target_dir}/{version_info_notebook.path}"
            version_info_source = self.client.workspace().export_notebook(version_info_target)
            if verbose: print("-"*80)
            if verbose: print(f"Backed up .../{version_info_notebook.path}")
        except Exception:
            if verbose: print("-"*80)
            if verbose: print(f"An existing copy of .../{version_info_notebook.path} was not found to backup")
            version_info_source = None  # It's OK if the published version of this notebook doesn't exist

        # Now that we backed up the version-info, we can delete everything.
        target_status = self.client.workspace().get_status(self.target_dir)
        if target_status is None:
            pass  # Who cares, it doesn't already exist.
        elif mode == "no-overwrite":
            assert target_status is None, "The target path already exists and the build is configured for no-overwrite"
        elif mode == "delete":
            if verbose: print("-"*80)
            if verbose: print(f"Deleting target directory...")
            self.client.workspace().delete_path(self.target_dir)
        elif mode.lower() != "overwrite":
            if verbose: print("-"*80)
            if verbose: print(f"Overwriting target directory (unused files will not be removed)...")
            raise Exception("Expected mode to be one of None, DELETE or OVERWRITE")

        # Determine if we are in test mode or not.
        try:
            testing = version_info_source is not None and testing
        except:
            testing = False

        for notebook in main_notebooks:
            notebook.publish(source_dir=self.source_dir,
                             target_dir=self.target_dir,
                             verbose=verbose, 
                             debugging=debugging,
                             other_notebooks=self.notebooks)

        if testing:
            print("-" * 80)  # We are in test-mode, write back the original Version Info notebook
            version_info_path = f"{self.target_dir}/Version Info"
            print(f"RESTORING: {version_info_path}")
            self.client.workspace().import_notebook("PYTHON", version_info_path, version_info_source)
        else:
            version_info_notebook.publish(source_dir=self.source_dir,
                                          target_dir=self.target_dir,
                                          verbose=verbose, 
                                          debugging=debugging,
                                          other_notebooks=self.notebooks)
        print("-"*80)
        print("All done!")

    def create_publish_message(self, name, version, source_repo, target_dir, domain="curriculum-dev.cloud.databricks.com", workspace_id="3551974319838082"):
        message = f"""
@channel Published {name}, v{version}

Release Notes:
* UPDATE FROM CHANGE LOG

Release notes, course-specific requirements, issue-tracking, and testing-results for this course can be found
in the course's GitHub repository at https://github.com/databricks-academy/{source_repo.split("/")[-1]}

Please feel free to reach out to me (via Slack) or anyone on the curriculum team should you have any questions.""".strip()

        return f"""
        <body>
            <p><a href="https://{domain}/?o={workspace_id}#workspace{target_dir}/Version Info" target="_blank">Published Version</a></p>
            <textarea style="width:100%" rows=11> \n{message}</textarea>
        </body>"""
import sys
print(f"[[[ {__name__} ]]]")
sys.modules["dbacademy.dbpublish"] = __import__("dbpublish")

print("*" * 80)
print("* DEPRECATION WARNING")
print("* The package \"dbacademy.dbpublish\" has been moved to \"dbacademy_courseware.dbpublish\".")
print("*" * 80)

import sys

dbacademy = sys.modules["dbacademy"]
dbacademy["dbtest"] = __import__("dbacademy_courseware.dbtest")

print("*" * 80)
print("* DEPRECATION WARNING")
print("* The package \"dbacademy.dbtest\" has been moved to \"dbacademy_courseware.dbtest\".")
print("*" * 80)

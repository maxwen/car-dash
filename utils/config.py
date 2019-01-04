'''
Created on Dec 6, 2011

@author: maxl
'''
import configparser

class Config():
    def __init__(self, fileName):
        self.config=configparser.ConfigParser()
        self.fileName=fileName
        self.readConfig()

    def writeConfig(self):
        with open(self.fileName, 'w') as configfile:
            self.config.write(configfile)

    def readConfig(self):
        self.config.read(self.fileName)

    def getDefaultSection(self):
        return self.config["DEFAULT"]

    def getSection(self, section):
        if self.hasSection(section):
            return self.config[section]
        return self.getDefaultSection()

    def addSection(self, section):
        self.config.add_section(section)

    def hasSection(self, section):
        return self.config.has_section(section)

    def removeSection(self, section):
        self.config.remove_section(section)

    def set(self, section, key, value):
        self.config.set(section, key, value)

    def get(self, section, key):
        return self.config.get(section, key)

    def items(self, section):
        return self.config.items(section)

    def testConfig(self):
        for item in self.config.items("DEFAULT"):
            print(item)

if __name__ == "__main__":
    c=Config("test.cfg")
    c.readConfig()
    c.testConfig()
    c.writeConfig()


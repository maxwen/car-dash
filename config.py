'''
Created on Dec 6, 2011

@author: maxl
'''
import configparser

class Config():
    def __init__(self):
        self.config=configparser.ConfigParser()
        self.fileName="candash.cfg"
        self.readConfig()
        
    def writeConfig(self):
        with open(self.fileName, 'w') as configfile:
            self.config.write(configfile)
    
    def readConfig(self):
        self.config.read(self.fileName)
    
    def getDefaultSection(self):
        return self.config["DEFAULT"]
    
    def testConfig(self):
        for item in self.config.items("DEFAULT"): 
            print(item)

if __name__ == "__main__":
    c=Config()
    c.readConfig()
    c.testConfig()
    c.writeConfig()


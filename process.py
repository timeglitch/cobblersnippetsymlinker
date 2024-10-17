#This program processes a file called md5hashes.txt
#and a the local directory filled with the config files
#outputs template files, without duplicates
#The outputted template files are semantically named
#Then creates symlinks to replace the original disk configs.
#All disk configs filenames must start with disk_config_ 
#run with python3.6 or later preferably


import json
import re
import shutil
import os
from statistics import mode, StatisticsError
import collections

#i should use a better directory system but whatever
disk_config_dir = './'
disk_template_dir = './disk_templates'
old_dir = './disk_templates/old'

addMessages = False #add comments on top of created templates

os.system("md5sum disk_config_* > md5hashes.txt")
f = open("md5hashes.txt", "r")  # created this file using bash >>> md5sum disk_config_* > md5hashes.txt
lines = f.readlines()
 
hashes = dict()
#each entry has three items
# [0] is the count of hosts
# [1] is the text of the config files of the hosts
# [2] is the list of the names of the config files

for line in lines:
    md5, hostname = line.split()
    if md5 in hashes:
        hashes[md5][2].append(hostname)
        hashes[md5][0] += 1
    else:
        with open(hostname,'r') as f:
            hashes[md5] = [1, f.read(), [hostname]]

for md5 in hashes:
    hashes[md5][2].sort()

with open('hashdict.json','w') as f:
    f.write(json.dumps(hashes))

with open('hashdict.json','r') as f:
    hashes = json.load(f)
    print("saved and loaded")

#print(hashes["939b94767f97732b2a4758873a0f252b"])  #exaple hashes entry

#requires a disk_templates folder to exist and a old folder to exist in the disk_templates folder.
#im using an 'old' folder instead of deleting old information
#probably will just delete the 'old' folder when done

file_names = [f for f in os.listdir(disk_template_dir) if os.path.isfile(f)] #list all files
for file_name in file_names:
    shutil.move(os.path.join(disk_template_dir, file_name), os.path.join(old_dir, file_name))



#========================creating template files=======================================
hostTypePattern = "^disk_config_(.+?)[\d]*(\.\w+)*$"
createdFileNameList = [] #keep track of duplicate file names
md5totemplate = dict()  #create table to go from md5 hash to template name

debugCount = 0 #how many loop iterations to print debug statements for

for md5 in hashes:
    debugCount -= 1

    numHosts = hashes[md5][0]
    contents = re.sub(r'^#.*\n?', '', hashes[md5][1], flags=re.MULTILINE)  
    filename = ""  #initialize empty string to add on to.
    if debugCount > 0:
        print("=================BEFORE=====================")
        print(hashes[md5][1])
        print("==================AFTER=====================")
        print(contents)


    #need to filter contents so that lines starting with '#' are ignored
    if "efi" in contents:
        filename += "EFI_"
    elif "biosboot" in contents:
        filename += "BIOS_"
    else:
        filename += "UNK_"

    disktype = ""
    if "sdb" in contents:
        disktype = "twodisk"
    elif "vda" in contents:
        disktype = "vdisk"
    elif "sda" in contents:
        disktype = "onedisk"

    if "nvme" in contents:
        disktype += "nvme"

    if len(disktype) == 0:
        disktype = "UNK_DISK"
    filename += disktype +  "_"

    typeNames = [re.search(hostTypePattern, name).group(1) for name in hashes[md5][2]] #remove the url and the number and only keep the name type

    if numHosts == 1:
        hosttype = hashes[md5][2][0].split(".")[0][12:]  #remove the url but keep the full name for a single server
    elif numHosts == 2:
        if typeNames[0] == typeNames[1]:
            hosttype = mode(typeNames)
        else:
            hosttype = typeNames[0] + "&" + typeNames[1]
    else:
        #print(hashes[md5][2])
        try:
            hosttype = mode(typeNames)
        except StatisticsError:  #Catches error if there are multiple modes. In python 3.8 or later, it would just return the first mode, so the code would work
            hosttype = typeNames[1]  #just pick the second hosttype, can't be bothered to do anything more complex


    filename += hosttype + "_"

    dockerMatch = re.search("#.*(\d\d+).*docker", hashes[md5][1]) #can't search through contents since I want to read the comments, maybe change this line to read the actual docker assignment line
    
    if dockerMatch:  #report docker size
        filename += "docker" + str(dockerMatch.group(1)) + "_"

    if numHosts == 1:
        filename += "UNIQ-HOST"
    elif numHosts == 2:
        filename += "2COUNT-HOST"
    elif numHosts < 10:
        filename += "FEW_HOST"
    elif numHosts < 25:
        filename += "SOME_HOST"
    elif numHosts < 100:
        filename += "MANY-HOST"
    else:
        filename += "VERYMANY-HOST"

    
    if filename in createdFileNameList:
        filename += "_ALT" + str(numHosts)
        if False or debugCount > 0:
            print(filename + " duplicate")
            print(md5)
            print(hashes[md5][2][0])
            print()
            #createdFileNameList.append(filename)  #helped get rid of name collisions

            #continue #this line used to be here to make sure i could see both files that had the samename
    createdFileNameList.append(filename)  #helped get rid of name collisions
    
    md5totemplate[md5] = disk_template_dir + '/' + filename + ".conf"
    with open(disk_template_dir + '/' + filename + ".conf",'w') as f:
        if addMessages:
            f.write("## " + str(hashes[md5][2]) + "\n")
            f.write("## are the hostnames.\n")
            f.write("## Number of hosts using this template" + str(numHosts) + " \n")
            f.write("## hash for this template is: " + md5 + "\n")
            f.write("## all text above this line was written automatically at template creation and is not updated")
            #f.write("##: the automatically calculated host type is: " + str(typeNames) + "\n")
            #f.write("## the automatically calculated filename is: " + filename + "\n")
        f.write(hashes[md5][1])

duplicates = [item for item, count in collections.Counter(createdFileNameList).items() if count > 1]
print("Duplicates: " + str(len(duplicates)))
print(duplicates)
print("Number of templates: " + str(len(createdFileNameList)))

#=================================Creating Symlinks=====================================

for md5 in hashes:
    templateLocation = md5totemplate[md5]
    
    for conf in hashes[md5][2]:
        print(disk_config_dir + "/" + conf)
        print(templateLocation)
        os.remove(disk_config_dir + "/" + conf)
        os.symlink(templateLocation, disk_config_dir + "/" + conf)
        if not os.path.isfile(conf):
            print("NOT A FILE: " + conf)

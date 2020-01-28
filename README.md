# hearham-uploader
Hearham uploader software

# Requirements

2GB free disk space
Any recent Ubuntu/debian should work.
SDR device for input is recommended.

# Setup
Run "./setup.sh" once to download and compile all necessary files. May take 10min or so.

Run ./HearHamUploader.py to start the recognizer.

hear.config has some options you may want to try, there are many options in the referenced .jconf files too.

# Running

With a radio next to the mic (or better yet, SDR software and the audio loopback described here: https://www.youtube.com/watch?v=RSeINGM68A8)
you should see text roughly equivalent to what is spoken. When it's set up, enter your secret upload key that you got when setting up a channel on hearham.com. It should be noted that the server side software does take into account *almost* matching and phonetics - Charlie Oscar Oscar Lima! 

# Research
The system in its current form tells what words you are saying but has a hard time distinguishing letters especially, and anything with static, as is common on the radio. There are various other systems that would be worth a look for anyone researching speech-to-text:

* Mozilla DeepSpeech
* Kaldi
* GoVivaci
* Google Cloud
* Houndify
* IBM Watson
* Microsoft Azure

and others?? That's just a list based on [Mycroft's](https://mycroft-ai.gitbook.io/docs/using-mycroft-ai/customizations/stt-engine), some paid and some free. 

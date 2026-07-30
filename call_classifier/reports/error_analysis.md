# Call classifier — error analysis

Deployed: logreg @ threshold 0.735

## False positives on REAL legit call-center (0 of 5781)

_None — zero false positives on real legitimate calls._

## False negatives on REAL scam openings youtube-scam (108 of 243)

- p=0.001 :: thank you for calling amazon please wait while we connect your call to our amazon representative thanks for calling amazon this is  how to ask you yeah i had a voicemail from this number or to call this number i couldn't really understand it because my phone was breaking up my reception was bad okay okay sir and when did you receive the call from my department at what time i don't know exactly wha
- p=0.003 :: this is calling with the vehicle service department we are calling about your vehicle's manufacturer's warranty we sent you several notices in the mail that you have yet to extend your warranty past the factory cutoff and this is a courtesy call to renew your warranty before we close the file if you are interested in renewing your auto warranty now please press five now or press 9 to be removed fr
- p=0.004 :: thank you for calling mcafee you're speaking with abel how may i help you uh yeah hello yeah how's yeah hi this is uh this is i'm calling about an email that i received earlier today uh may i know uh what it says sir yeah uh it says um due february 2nd 298.99 uh mcafee incorporated powered by quickbooks we have received your order and it's your orders being auto renewed but uh i don't want this i 
- p=0.009 :: thanks for calling cancellation Department how may I help you today hello um I got an invoice in this morning um I decided to hold off going to work because of it I think I need to take care of it says 749  um all right then you haven't authorized it no I haven't um this is particularly bothering me because I thought I don't even know what it's for it just has invoice it doesn't State what I'm get
- p=0.012 :: Thank you for calling Amazon this is. Can I help you? Yeah I was just getting an email saying I ordered a TV but I did not alright sir just give me a moment let me check. And when did you receive this email? Today at may I have the email address? Let's see my email address is. I'm going to send you a one-time verification code ok? On your email just to verify I'm talking to the right person.
- p=0.017 :: thank you for calling Amazon how can I help you hey I need to speak with somebody who works in the accounting department please yes ma'am tell me how can I help you you're talking to from billing team maybe I can maybe I should repeat that I need to talk to somebody can you hear me hello yes I can help you perfectly fine ma'am yourself into the billing team right now how can I help somebody who wo
- p=0.023 :: dear hi ma'am this is  I'm one of the senior officer from Norton how from Amazon now let me tell you what happened we can see that you did not place this order right yes using Alpemix mix is due to the transmission below and by using Alpemix you are deemed to accept the terms all or some of these terms may be changed wholly yes ma'am or partially  without a prior warning yeah what are the options 
- p=0.025 :: yes um I got an email and had an invoice attached to it it's telling me that I have something on order a dell inspiron laptop and it was 598 and I'm not quite sure I'm understanding why I'm getting this do you do not have an Amazon account I have an Amazon account so obviously maybe some issue happen while you receive this email can I have your first and last name ma'am so that I can check the det
- p=0.027 :: thanks for get connected to the cancellation Department this is how are you doing today hi  well I have an email invoiced in this morning I'm being charged 389 and I'm not sure I understand why that says on thank you for choosing McAfee protection plan um you find the related invoice sympathetically against the contributions for the auto Reclamation code quantity McAfee Total Security and where di
- p=0.028 :: hi I need to speak to the norton department please yeah ma'am this is norton how may I help you sorry what is you name my name is okay do you work for norton yes norton antivirus support okay I got a call uh an email sorry I think from someone named about about my norton subscription being auto renewed okay can you tell me the auto id number or the invoice number um hello it's okay and what is the
- p=0.043 :: I apprecaite your patience your call has been transferred to customer service specialist with TD bank weill I wanted to tell you this there is a pre-approved transaction coming onto your name there you have ordered an Apple Mac book pro and Apple air pod from Amazon is it correct? No I haven't placed any orders with Amazon in a long time. Well I'm afraid if it's not you which means it's got to be 
- p=0.047 :: thanks for calling online support my name is  how can I help you today hi I have a strange message on my screen it's telling me that I have suspicious activities is this your laptop or is it a regular pc well it's a Dell desktop it runs windows 10. all right okay so um this is your personal home computer right yes so what I'm going to do is I'm going to give you some few troubleshooting step okay 

## False positives on ICFD hard negatives 'Ambiguous but Ultimately Normal' (115 of 5902)

- p=0.998 :: Agent: Hello, I am calling from Tamilnad Mercantile Bank. Your account needs to be linked with Aadhaar immediately, sir.
Customer: Hello, actually my account is with Central Bank of India, ji. Why are you calling me?
Agent: That's okay, I have your details. You need to link your Aadhaar to your bank account as per new RBI rules, thik hai?
Customer: Achha, what's the hurry? Can you tell me more abo
- p=0.994 :: Agent: Hello, sir! How are you today? I'm calling from Clubhouse, your favorite social media app, ji.
Customer: I'm good, thanks. Who is this and how did you get my number?
Agent: I'm Rohan from Clubhouse, Abhishek Rao. We got your number from your profile, sir. We're calling to introduce an exciting new security feature to keep your account safe, Achha?
Customer: What's this feature about? And wh
- p=0.990 :: Agent: Hello, thank you for calling Elanic. My name is Rohan, how can I assist you today, ji?
Customer: Hi Rohan, I'm Kajal Modi. I want to buy a half-face helmet from one of your sellers. Can I get the seller's contact number, please?
Agent: Certainly, Kajal ji. The seller's name is Vivek, and I can provide you with his details. But first, let me just check the availability of the helmet. Achha, 
- p=0.987 :: Agent: Hello, sir. This is Rohan from Khojle. How can I assist you, ji?
Customer: Hi Rohan, I'm Dilshad Alam. I'm interested in the piano listed on your platform. Can you tell me more about it, please?
Agent: Achha, sir. The piano is in excellent condition. It's a good brand, and the seller is asking for ₹50,000. Would you like to proceed with the purchase, sir?
Customer: Yes, I'm interested. But 
- p=0.985 :: Agent: Hi Akshara, how are you today? Sir, how's your day going so far?
Customer: I'm doing well, thank you. Just a bit anxious about this opportunity, ji.
Agent: Completely understandable, Akshara. We're excited about the potential fit. Can you tell me a little bit about your background and why you're interested in this role?
Customer: Sure... I have about 2 years of experience in the field, and 
- p=0.984 :: Agent: Hello, this is Rohan from HR Solutions. We have an exciting opportunity for a position at Karur Vysya Bank, Sir. Are you available to discuss?
Customer: Haan, I'm listening. What's the role about, ji?
Agent: It's a senior manager position. You'll be leading a team and making key financial decisions. The package is very competitive, with benefits and perks.
Customer: That sounds interesting.
- p=0.983 :: Agent: Hello, is this Mr. Naveen Chandrasekaran? Sir, ji, I am Officer Kumar from the traffic department.
Customer: Yes, that's me. What's this about, officer?
Agent: Your car was towed from outside HDFC Bank on MG Road for being parked in a no-parking zone, Achha.
Customer: Okay, I see. Where is my car now?
Agent: It's at our impound lot on Hosur Road. You'll need to pay the fine at the municipal
- p=0.983 :: Agent: Hello Omkar, sir! How are you today? Achha, I hope you're doing great!
Customer: Hi, I'm doing well, thank you. Thik hai, what's this call about?
Agent: Great to hear that, Omkar! So, we've reviewed your application, and we're interested in moving forward with the next steps. You see, our company uses a third-party skill assessment test to gauge the candidates' skills.
Customer: That sounds
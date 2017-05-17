
**Note Unreleased means it haven't been pushed to PyPi** 

## Version 0.2.0 [Unreleased]
- Enabled option to not received reply/response from sphero to save bandwidth from ``command``
- All standard functions now have the option of blocking which waits for sphero to send a response, If set to no response/block, sphero will not send back a comfirmation reply(simple response) at all. All functions that doesn't return a response will be set to false by default
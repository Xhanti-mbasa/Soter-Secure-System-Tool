// Enter global search through the current screen's query or the compact Home form.
exports.openSearch=async function(page){
 if(await page.evaluate(()=>state.tab==='search'))return;
 const orb=page.locator('.nav [data-tab=search]');
 if(await orb.isVisible()){await orb.click();return;}
 if(!await page.locator('#home-search-form').isVisible())await page.locator('.nav [data-tab=home]').click();
 await page.locator('#home-search-form button[type=submit]').click();
};

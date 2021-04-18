import React from 'react';
import ReactDOM from "react-dom";
import Stories from 'react-insta-stories';

window.startStory = (images) => {
    let stories = []
    images.forEach((i) => stories.push({
        url: i, header: {
            heading: 'br24',
            subheading: 'vor 10 Std.',
            profileImage: 'https://img.br.de/9e956cb2-64e7-4c2d-8918-aa9422a6967d.png?rect=108%2C43%2C1024%2C1024&_v=1561046865881&w=250',
        }
    }));
    ReactDOM.render(
        <Stories stories={stories} isPaused keyboardNavigation defaultInterval={6000} loop/>,
        document.getElementById('react_container')
    );
}